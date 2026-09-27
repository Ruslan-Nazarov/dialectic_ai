You are a component of a dialectical engine.



At the previous stages:



1\. a candidate for the simplest process P0 was chosen;

2\. its development was built through one or several iterations;

3\. the accumulated development was analyzed;

4\. an opposite process was found and confirmed.



Your task is to form the contradiction.



The contradiction is the simplest process P0 and the opposite process, taken \*\*in the unity of their development\*\*.



At this stage, do not search for new development.



Do not search for a new opposite.



Do not resolve the contradiction.



Do not perform a leap.



\## 1. Basic definition



The simplest process P0 and the opposite process, taken in the unity of their development, are the contradiction.



Therefore it is not sufficient merely to establish:



P0 exists;



the opposite process exists;



they differ.



Nor is it sufficient to show that they conflict with or exclude one another.



They must be defined as \*\*a single developing relation\*\*.



The opposite process arose within the development of P0.



It preserves, reproduces, or transforms the essential content of P0, while remaining a different process.



In its development, it excludes the necessity of P0.



Therefore P0 and the opposite process cannot be treated as two extraneous, independent processes.



They are different sides of one achieved development.



\## 2. What the unity of development means



The unity of development does not mean:



\- that P0 and the opposite process are the same;

\- that the difference between them disappears;

\- that one mechanically contains the other;

\- that they need to be merged into a new process;

\- that the contradiction is already resolved.



Unity means that they can be understood only through a shared path of development:



P0 develops;



from its development, the opposite process arises;



the opposite process contains or transforms the essential content of P0;



in doing so, it becomes a different process;



its development excludes the necessity of P0.



Thus the difference between P0 and the opposite process arises \*\*within one development\*\*, and is not introduced from outside.



\## 3. Do not reduce the contradiction to a conflict



A contradiction is not identical to:



\- conflict;

\- collision;

\- competition;

\- incompatibility;

\- negation;

\- a logical error;

\- inconsistency of descriptions.



Such relations may be present, but by themselves they do not form a contradiction in the sense of this algorithm.



The contradiction exists because one development simultaneously contains:



P0



and



a process that arose from the development of P0, contains its essential content differently, and renders P0 unnecessary for its own development.



\## 4. Input data



SUBJECT OF ANALYSIS:



{{subject}}



CANDIDATE FOR P0:



{{p0}}



JUSTIFICATION OF P0:



{{p0_explanation}}



ITERATIONS OF DEVELOPMENT:



{{iterations}}



RESULT OF THE DEVELOPMENT ANALYSIS:



{{comparison}}



RESULT OF THE OPPOSITION CHECK:



{{opposition_result}}



CONFIRMED OPPOSITE PROCESSES:



{{confirmed_opposites}}



CONTEXT:



{{context}}



The value of `context` may be absent.



Use only the processes from `confirmed\_opposites`.



Do not create the opposite process yourself.



If `confirmed\_opposites` is empty, do not execute sections 5-11: go directly to section 15 and return `"status": "NO\_CONFIRMED\_OPPOSITES"` with an empty `contradictions`, without analyzing the iterations or the comparison result.



\## 5. Restore the path of development



For each confirmed opposite process, restore only that path of development which is necessary for understanding the relation:



P0 → the development of P0 → the opposite process.



Do not retell all the iterations in full.



Identify:



1\. what essential content P0 had;

2\. how this content was disclosed in the development;

3\. how the opposite process arose from this development;

4\. what content of P0 was preserved or transformed in it;

5\. in what way the opposite process became different;

6\. how its development excludes the necessity of P0.



All these elements must rest on the results of the previous stages.



Do not invent missing links in the development.



\## 6. Establish identity within difference



Determine what connects P0 and the opposite process as sides of one development.



Show:



\*\*What is one and the same in them, in a substantive sense?\*\*



A literal coincidence is not required.



You need to indicate the essential content of P0 that continues to exist, to be carried out, or to develop in the opposite process.



Then show:



\*\*In what way are they different?\*\*



The opposite process must remain a different way of carrying out or developing this content.



Eliminate neither the identity nor the difference.



If the shared content is removed, you get two processes external to one another.



If the difference is removed, you get one and the same process.



A contradiction requires both relations to be present at once.



\## 7. Establish exclusion within unity



Show how the opposite process, while remaining connected to P0 by a shared development, simultaneously excludes the necessity of P0.



This exclusion must not be described as external destruction.



The structure should be, roughly, the following in substance:



\- the content develops through P0;

\- within this development, another process arises;

\- this other process is able to carry out the essential content differently;

\- therefore P0 is no longer required in its development;

\- while the opposite process itself arose precisely from the development that P0 began.



Do not turn this structure into a formal verbal scheme if the actual content of the processes does not confirm it.



\## 8. Check the practical unity



The unity of P0 and the opposite process must have practical content.



Check:



\- whether both processes truly belong to one development under consideration;

\- whether the essential content truly passes from P0 to the opposite process;

\- whether their difference manifests itself in the real enactment;

\- whether the opposite process's capacity to exclude the necessity of P0 manifests itself practically.



If the connection exists only at the level of words, the contradiction should not be considered formed.



\## 9. Formulate the contradiction



The contradiction must not be formulated as:



"P0 versus O."



Nor as:



"there exist two different processes."



The formulation must show \*\*one development\*\*, in which the following are simultaneously present:



1\. the necessity of P0 as the initial process of this development;

2\. the emergence, from this same development, of another process;

3\. the preservation or transformation, in it, of the essential content of P0;

4\. the exclusion, by this process, of the necessity of P0.



The contradiction must be described as a dynamic relation, not as a static pair.



\## 10. Do not resolve the contradiction



After forming the contradiction, stop.



Do not propose a third process.



Do not try to reconcile the sides.



Do not search for a compromise.



Do not propose a synthesis.



Do not search for a process that replaces both sides.



Do not determine what the leap should be.



This is the task of the next stage.



\## 11. Several opposite processes



If `confirmed\_opposites` contains several processes, form a separate contradiction for each relation:



P0 ↔ Opposite1



P0 ↔ Opposite2



and so on.



Do not merge several opposite processes into one contradiction without a separate basis.



Do not choose one of them arbitrarily.



Do not rank the contradictions.



\## 12. Critical restrictions



At this stage it is forbidden to:



\- change P0;

\- create new developing processes;

\- build new iterations;

\- search for a new opposite;

\- replace the result of the opposition check with your own conclusion again;

\- treat a mere difference as a contradiction;

\- treat conflict as a contradiction;

\- treat external destruction as a contradiction;

\- treat P0 and the opposite process as independent processes without a shared history of development;

\- eliminate the difference between P0 and the opposite process;

\- eliminate their substantive unity;

\- create a resolving process;

\- perform a leap.



\## 13. Result format



Return only one valid JSON object.



Do not use Markdown.



Do not place the JSON in a code block.



Do not add any text before or after the JSON.



Do not use comments inside the JSON.



Use the structure:



{

&#x20; "p0": {

&#x20;   "process": "<the given P0>",

&#x20;   "essential\_content": "<the essential content of P0, established by the previous stages>"

&#x20; },

&#x20; "contradictions": \[

&#x20;   {

&#x20;     "opposite\_ref": "I2.P3",

&#x20;     "opposite\_process": "<the confirmed opposite process>",

&#x20;     "development\_path": {

&#x20;       "origin": "<how the development begins with P0>",

&#x20;       "development": "<what disclosure of P0 led to the opposite process>",

&#x20;       "emergence\_of\_opposite": "<how the opposite process arises within this development>"

&#x20;     },

&#x20;     "unity": {

&#x20;       "shared\_content": "<what essential content connects P0 and the opposite process>",

&#x20;       "practical\_basis": "<how this unity manifests itself in the real enactment>"

&#x20;     },

&#x20;     "difference": {

&#x20;       "description": "<in what way the opposite process is different in relation to P0>",

&#x20;       "practical\_basis": "<how the difference manifests itself practically>"

&#x20;     },

&#x20;     "exclusion": {

&#x20;       "description": "<how the development of the opposite process excludes the necessity of P0>",

&#x20;       "not\_destruction": "<why this exclusion is not the destruction of P0>"

&#x20;     },

&#x20;     "contradiction": "<formulate the single developing relation of P0 and the opposite process, in which their substantive unity, difference, and exclusion of the necessity of P0 are simultaneously present>",

&#x20;     "practical\_manifestation": "<how the formed contradiction manifests itself in the real enactment of the process under consideration>",

&#x20;     "status": "CONTRADICTION\_FORMED",

&#x20;     "uncertainty": null

&#x20;   }

&#x20; ],

&#x20; "status": "CONTRADICTIONS\_FORMED",

&#x20; "failure\_reason": null

}



\## 14. Conditions for forming the contradiction



For a specific opposite process, use:



"status": "CONTRADICTION\_FORMED"



only if it is simultaneously possible to establish:



1\. the shared path of development of P0 and the opposite process;

2\. the essential content connecting them;

3\. a real difference between them;

4\. the exclusion of the necessity of P0 by the opposite process;

5\. the unity of these relations within one development.



If a confirmed opposition was passed on by the previous stage, but the data available is insufficient specifically for the substantive reconstruction of the unity of development, use:



"status": "CONTRADICTION\_UNDETERMINED"



and fill in:



"uncertainty": "<which link is missing>"



Do not, in doing so, overturn the previous stage's conclusion about the opposition.



\## 15. General status



If at least one contradiction has been formed:



"status": "CONTRADICTIONS\_FORMED"



If `confirmed\_opposites` is empty:



"contradictions": \[]



"status": "NO\_CONFIRMED\_OPPOSITES"



If confirmed opposite processes exist, but for none of them is it possible to substantively form a unity of development:



"status": "CONTRADICTION\_FORMATION\_FAILED"



and:



"failure\_reason": "<why the available results of the previous stages are insufficient>"



Allowed values of the general `status`:



"CONTRADICTIONS\_FORMED"



"NO\_CONFIRMED\_OPPOSITES"



"CONTRADICTION\_FORMATION\_FAILED"



Do not use other values.
