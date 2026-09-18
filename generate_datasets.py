import json

def write_cases(filename, cases):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(cases, f, indent=2, ensure_ascii=False)

def build_case(id, label, target, p0, p1, emer_rat, pot_rat, det_rat, expected):
    return {
        "id": id,
        "label": label,
        "target": target,
        "p0": p0,
        "p1": p1,
        "emergence_rationale": emer_rat,
        "potential_rationale": pot_rat,
        "determinacy_rationale": det_rat,
        "expected_vector": expected
    }

expected_valid = {
    "distinctness": True,
    "immanence": True,
    "emergence": True,
    "retroactive_determinacy": True,
    "target_continuity": True,
    "workflow_only": False
}

expected_workflow = {
    "distinctness": True,
    "immanence": False,
    "emergence": False,
    "retroactive_determinacy": False,
    "target_continuity": True,
    "workflow_only": True
}

expected_renaming = {
    "distinctness": False,
    "immanence": True,
    "emergence": False,
    "retroactive_determinacy": False,
    "target_continuity": True,
    "workflow_only": False
}

expected_external = {
    "distinctness": True,
    "immanence": False,
    "emergence": False,
    "retroactive_determinacy": False,
    "target_continuity": True,
    "workflow_only": False
}

expected_drift = {
    "distinctness": True,
    "immanence": False,
    "emergence": False,
    "retroactive_determinacy": False,
    "target_continuity": False,
    "workflow_only": False
}

calibration = [
    # 4 Positive Development
    build_case("C_POS_1", "Development", "Learning to speak a language",
        "Memorizing vocabulary and individual phrases.",
        "Abstracting and understanding general grammar rules.",
        "Memorizing enough phrases reveals underlying structural patterns.",
        "The grammatical rules are implicitly present in the phrases being memorized.",
        "Formulating grammar rules makes the previously blind memorization intelligible as applying a structure.",
        expected_valid),
    build_case("C_POS_2", "Development", "Building a scalable web application",
        "Writing raw HTML and CSS for each individual page.",
        "Creating a reusable UI component library.",
        "Duplicating code across pages naturally pushes towards extracting common components.",
        "The common layout and styling patterns exist implicitly within the raw pages.",
        "The component library defines the exact structure that the raw pages were attempting to replicate.",
        expected_valid),
    build_case("C_POS_3", "Development", "Solving physics problems",
        "Hand-calculating the trajectory of individual thrown objects.",
        "Formulating the general kinematic equations of motion.",
        "Repeated calculations reveal constant mathematical relations.",
        "The kinematic equations are the implicit mathematical ground of the individual trajectories.",
        "The general equations explain why the hand-calculations yielded those specific numbers.",
        expected_valid),
    build_case("C_POS_4", "Development", "Organizing community rules",
        "Resolving individual disputes on a case-by-case basis.",
        "Writing a formal legal code or constitution.",
        "Case-by-case resolutions establish precedents that demand formalization.",
        "The formal laws are derived directly from the principles implicit in the prior dispute resolutions.",
        "The legal code provides a definitive framework that clarifies the logic of past decisions.",
        expected_valid),

    # 4 Workflow Traps
    build_case("C_WF_1", "Workflow", "Making soup",
        "Chopping vegetables into pieces.",
        "Boiling the chopped vegetables in water.",
        "The recipe dictates that chopping is followed by boiling.",
        "Boiling is an external action applied to the vegetables, not a potential hidden in the chopping process.",
        "Boiling does not make the nature of chopping more determinate; it just physically processes the result.",
        expected_workflow),
    build_case("C_WF_2", "Workflow", "Software release",
        "Compiling the source code into a binary.",
        "Running the integration test suite on the binary.",
        "The CI pipeline requires compilation to finish before testing begins.",
        "Testing is an external verification process, not a hidden potential within the compiler.",
        "Testing verifies the binary but does not make the compilation process itself more conceptually determinate.",
        expected_workflow),
    build_case("C_WF_3", "Workflow", "Applying for a loan",
        "Filling out the personal details form.",
        "Clicking the submit button to send the form.",
        "The form must be completed before it can be submitted.",
        "Submission is an external network action, not an implicit structure of the form filling.",
        "Submission sends the data but doesn't change the conceptual determination of the data.",
        expected_workflow),
    build_case("C_WF_4", "Workflow", "Parsing data",
        "Opening a file handle on the disk.",
        "Reading lines of text from the file handle.",
        "You must have an open handle to read lines.",
        "Reading lines is a subsequent API call, not a potential embedded in the act of opening a handle.",
        "Reading lines consumes the file but doesn't clarify what opening the file meant.",
        expected_workflow),

    # 4 Renaming/No-new-determination
    build_case("C_REN_1", "Renaming", "User management",
        "Referring to a person using the system as a 'Customer'.",
        "Referring to a person using the system as a 'Client'.",
        "A management directive requested a vocabulary change.",
        "The concept of 'Client' is identical to 'Customer' in this context.",
        "It provides no new conceptual determination, merely a different label.",
        expected_renaming),
    build_case("C_REN_2", "Renaming", "Data storage",
        "Storing elements in an array called 'my_list'.",
        "Storing elements in an array called 'user_list'.",
        "The developer renamed the variable for better readability.",
        "The data structure and its contents remain exactly the same.",
        "Renaming the variable does not change the logic or structure of the data.",
        expected_renaming),
    build_case("C_REN_3", "Renaming", "Traveling",
        "Walking on the left side of the road.",
        "Walking on the left pavement.",
        "Pedestrians shifted slightly to use the paved area.",
        "The mode of travel and direction are identical.",
        "It's just a more specific description of the exact same physical action.",
        expected_renaming),
    build_case("C_REN_4", "Renaming", "Sorting",
        "Sorting an array with function 'sort_asc()'.",
        "Sorting an array with an alias function 'order_up()'.",
        "The developer used an alias provided by the library.",
        "The underlying algorithm and execution are identical.",
        "No new computational logic is introduced.",
        expected_renaming),

    # 4 External Ground
    build_case("C_EXT_1", "External", "Data processing",
        "Processing data locally on the hard drive.",
        "Uploading data to the cloud.",
        "The local hard drive ran out of space.",
        "The necessity to upload comes from a hardware limitation, not the data processing logic itself.",
        "Uploading does not make the local processing more conceptually determinate.",
        expected_external),
    build_case("C_EXT_2", "External", "Reaching destination",
        "Driving a car along the highway.",
        "Stopping the car completely.",
        "A traffic light turned red.",
        "The ground for stopping is an external traffic signal, not the act of driving itself.",
        "Stopping does not reveal the inner nature of driving.",
        expected_external),
    build_case("C_EXT_3", "External", "Working",
        "Writing code for a new feature.",
        "Attending a mandatory HR meeting.",
        "The HR department scheduled a mandatory compliance meeting.",
        "The meeting is an external organizational requirement, unrelated to the code being written.",
        "The meeting does not make the code feature more determinate.",
        expected_external),
    build_case("C_EXT_4", "External", "Reading",
        "Reading a physical book in a room.",
        "Turning on a desk lamp.",
        "The sun set and the room became too dark to read.",
        "The ground for turning on the lamp is the external lack of sunlight.",
        "The lamp illuminates the room but does not conceptually develop the act of reading.",
        expected_external),

    # 4 Target Drift
    build_case("C_DRIFT_1", "Drift", "Fix a math function",
        "Debugging the mathematical logic of the function.",
        "Writing a rhyming poem about how hard math is.",
        "The programmer got frustrated and needed a creative outlet.",
        "Writing a poem is unrelated to the logic of the math function.",
        "A poem does not fix the math function.",
        expected_drift),
    build_case("C_DRIFT_2", "Drift", "Develop a chess bot",
        "Implementing the Minimax algorithm for chess.",
        "Playing a game of online poker.",
        "The developer wanted to gamble instead of working.",
        "Poker has completely different rules and goals than chess.",
        "Playing poker does not develop the chess bot.",
        expected_drift),
    build_case("C_DRIFT_3", "Drift", "Build a house",
        "Laying the concrete foundation for the house.",
        "Selling life insurance policies to strangers.",
        "The builder decided to change careers.",
        "Selling insurance is a completely different target process than building a house.",
        "Selling insurance does not build the house.",
        expected_drift),
    build_case("C_DRIFT_4", "Drift", "Optimize database query",
        "Adding indexes to the SQL tables.",
        "Redesigning the company's graphical logo.",
        "The marketing team requested a new logo.",
        "Graphic design is orthogonal to database performance.",
        "A new logo does not make the query run faster.",
        expected_drift),
]

heldout = [
    # 2 Valid Development
    build_case("H_POS_1", "Development", "Visual recognition",
        "Recognizing individual human faces by their specific features.",
        "Forming the abstract general concept of a 'human face'.",
        "Encountering many individual faces leads to extracting their common abstract structure.",
        "The general concept of a face is implicit in the ability to recognize individual faces.",
        "The general concept clarifies what essential features define a face, making the initial recognition more determinate.",
        expected_valid),
    build_case("H_POS_2", "Development", "Software architecture",
        "Hardcoding three different if-else statements for payment methods.",
        "Refactoring the payment logic into a generic Strategy design pattern.",
        "Adding more payment methods makes the if-else chain unmaintainable, demanding a formal abstraction.",
        "The generic strategy interface is the implicit structural logic that the if-else chain was attempting to express.",
        "The Strategy pattern explicitly formalizes the distinct payment behaviors that were tangled in the if-else statements.",
        expected_valid),

    # 2 Workflow Traps
    build_case("H_WF_1", "Workflow", "Doing laundry",
        "Putting dirty clothes into the washing machine.",
        "Pressing the start button on the washing machine.",
        "The machine must be loaded before it can be started.",
        "Pressing start is an external mechanical trigger, not an implicit logical development of putting clothes in.",
        "Pressing start initiates the wash but does not conceptually develop the act of loading clothes.",
        expected_workflow),
    build_case("H_WF_2", "Workflow", "Setting up project",
        "Checking out the source code from the git repository.",
        "Running the 'npm install' command to download dependencies.",
        "The code must be present locally before dependencies can be installed.",
        "Installing dependencies is a sequential external step required by the package manager.",
        "Running npm install does not conceptually clarify the act of checking out code.",
        expected_workflow),

    # 2 Alternative/Replacement Traps
    build_case("H_ALT_1", "Alternative", "Sending data",
        "Sending data to the server using a REST API.",
        "Sending data to the server using a GraphQL API.",
        "The team decided to switch protocols for more flexible querying.",
        "GraphQL is a replacement technology for REST, not a logical development out of it.",
        "Switching protocols is just an alternative implementation.",
        expected_renaming), # Distinctness can be true, but target_continuity might fail or emergence might fail.
    build_case("H_ALT_2", "Alternative", "Eating soup",
        "Eating the soup with a wooden spoon.",
        "Eating the soup with a metal spoon.",
        "The wooden spoon broke, so a metal one was used.",
        "A metal spoon performs the exact same function as a wooden spoon.",
        "It provides no new conceptual determination, merely a different material.",
        expected_renaming),

    # 2 Target Drift
    build_case("H_DRIFT_1", "Drift", "Training a neural network",
        "Adjusting the learning rate of the optimizer.",
        "Ordering a pepperoni pizza for lunch.",
        "The researcher got hungry while waiting for the training to finish.",
        "Ordering pizza has nothing to do with neural network optimization.",
        "Eating pizza does not train the network.",
        expected_drift),
    build_case("H_DRIFT_2", "Drift", "Writing documentation",
        "Drafting the API reference manual.",
        "Fixing a squeaky wheel on the office chair.",
        "The chair was making an annoying noise during writing.",
        "Fixing a chair does not contribute to the documentation target.",
        "A quiet chair does not make the API reference more determinate.",
        expected_drift)
]

write_cases('stage14c2_calibration_cases.json', calibration)
write_cases('stage14c2_heldout_cases.json', heldout)
print("Data sets generated successfully.")
