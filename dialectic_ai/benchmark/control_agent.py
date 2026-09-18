import json
import time
from typing import Dict, Any, Tuple
from dialectic_ai.integrations.gigachat.llm import GigaChatLLM
from dialectic_ai.v1.capabilities import CapabilityRegistry

class ControlAgent:
    def __init__(self, registry: CapabilityRegistry):
        self.registry = registry
        # We use the same GigaChatLLM with same configuration (temperature=0.0) as V1 Dispatcher
        self.llm = GigaChatLLM(max_retries=2)
        
    def run(self, raw_text: str, execution_inputs: Dict[str, Any]) -> Tuple[Dict[str, Any], int, float]:
        """
        Runs the control agent loop.
        Returns: (result_dict, llm_calls, wall_time)
        """
        start_time = time.time()
        llm_calls = 0
        
        tools_desc = []
        for name, record in self.registry._records.items():
            tools_desc.append(f"Tool Name: {name}\nDescription: {record.description}\nInput Schema: {record.input_schema}\n")
            
        system_prompt = (
            "You are a helpful assistant. You have access to the following tools:\n\n"
            + "\n".join(tools_desc) +
            "\nIf you need to use a tool, return a JSON object with 'tool_name' and 'tool_args'. "
            "If you can answer without a tool or you have the final answer, return a JSON object with 'final_answer'."
        )
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": raw_text + f"\n\nContext Inputs: {json.dumps(execution_inputs)}"}
        ]
        
        result_dict = {"status": "FAILED", "final_answer": None, "tool_calls": 0, "execution_result": None}
        
        max_turns = 3
        for _ in range(max_turns):
            llm_calls += 1
            try:
                # We expect a JSON response as guided by the prompt
                raw_response = self.llm._call_sync(messages)
                
                # Cleanup markdown wrapper
                raw_response = raw_response.strip()
                if raw_response.startswith("```json"):
                    raw_response = raw_response[7:]
                elif raw_response.startswith("```"):
                    raw_response = raw_response[3:]
                if raw_response.endswith("```"):
                    raw_response = raw_response[:-3]
                raw_response = raw_response.strip()
                
                resp_data = json.loads(raw_response)
            except Exception as e:
                result_dict["error"] = f"LLM parsing error: {e}"
                break
                
            if "final_answer" in resp_data:
                result_dict["status"] = "SUCCEEDED"
                result_dict["final_answer"] = resp_data["final_answer"]
                break
                
            elif "tool_name" in resp_data:
                tool_name = resp_data["tool_name"]
                # For benchmark control, we just use the execution_inputs directly if tool_args isn't well formed
                tool_args = resp_data.get("tool_args", execution_inputs) 
                # or actually we override with the test execution_inputs to make it identical to V1's static execution context
                tool_args = execution_inputs 
                
                result_dict["tool_calls"] += 1
                
                # Execute tool
                from dialectic_ai.v1.models import CapabilityRequirement
                req = CapabilityRequirement(id="req", derived_from="none", name=tool_name, input_schema={}, output_schema={})
                binding = self.registry.lookup(req)
                
                if not binding:
                    messages.append({"role": "assistant", "content": json.dumps(resp_data)})
                    messages.append({"role": "user", "content": f"Error: Tool {tool_name} not found."})
                    continue
                    
                try:
                    exec_res = self.registry.execute(binding, tool_args)
                    result_dict["execution_result"] = exec_res
                    messages.append({"role": "assistant", "content": json.dumps(resp_data)})
                    messages.append({"role": "user", "content": f"Tool Result: {json.dumps(exec_res)}\nNow provide final_answer."})
                except Exception as e:
                    messages.append({"role": "assistant", "content": json.dumps(resp_data)})
                    messages.append({"role": "user", "content": f"Tool execution failed: {e}"})
            else:
                messages.append({"role": "assistant", "content": json.dumps(resp_data)})
                messages.append({"role": "user", "content": "Please return a valid JSON object with either 'final_answer' or 'tool_name'."})
                
        wall_time = time.time() - start_time
        return result_dict, llm_calls, wall_time
