### **System Overview: The Living Instructions Protocol**

**Document Version:** 1.0 **Last Updated:** Thursday, June 26, 2025 at 10:40 PM EDT

#### **1\. Executive Summary**

The "Living Instructions Protocol" is a system designed to overcome the limitations of static, session-based instructions for AI agents. Its purpose is to create a persistent and evolving set of operational rules, personas, and configurations that can be collaboratively maintained and improved over time by a human user and an AI agent.

The system treats the AI's instructions not as a fixed prompt, but as a version-controlled configuration file. It provides a robust toolchain for the AI to manage, update, and validate this configuration in a safe and structured manner, with the human user acting as the final authority for all changes.

#### **2\. Core Design Philosophy**

* **Collaborative Evolution:** The AI's persona and ruleset are not static; they evolve through conversation and explicit agreement between the user and the AI.  
* **Programmatic Robustness:** All modifications to the instruction set are handled by a dedicated library of Python scripts, ensuring consistency and reliability.  
* **Structured & Validated Data:** All instructions are stored in a structured YAML format and validated against a formal schema, preventing errors from malformed configurations.  
* **Self-Contained History:** The instruction file itself contains a built-in audit trail of changes, providing context for future updates and merges.  
* **Human as Final Authority:** The AI can propose and prepare changes, but the human user performs the final "commit" by saving the updated master file.

#### **3\. System Components (The Files)**

This protocol is comprised of a data file, a schema, and a library of Python scripts. They are intended to reside together in the AI's "Knowledge" space.

**A. Data & Schema:**

* `master_instructions.yaml`: The single source of truth. This file contains the complete, current operational instructions for the AI agent.  
* `instructions_schema.yaml`: The "contract" or blueprint. It defines the required structure, data types, and keys for the `master_instructions.yaml` file, enabling automated validation.

**B. The Python Toolchain:**

* `helpers.py`: A shared module containing common functions (e.g., loading/saving YAML, timestamp generation) used by other scripts to avoid code duplication.  
* `validate.py`: Validates a given instruction file against the schema to ensure structural integrity.  
* `read_key.py`: Safely reads and displays the value of a specific key from the instructions file.  
* `update_key.py`: Updates the value of an existing key. It automatically archives the parent section's previous state before applying the change.  
* `add_item.py`: Adds a new item to a list within the instructions (e.g., adding a new rule).  
* `delete_item.py`: Deletes an item from a list by its index.  
* `prune.py`: Manages file size by trimming the inline history of archived sections based on a retention policy.  
* `merge.py`: Provides a mechanism to combine two divergent versions of the instruction file, flagging any direct conflicts for manual resolution.

**C. The Test Suite:**

* `test_*.sh`: A series of automated shell scripts, one for each Python tool, designed to run a simple "smoke test" to verify the script executes correctly and performs its basic function as expected.

#### **4\. Intended Use & Example Workflow**

This system enables a dynamic, multi-session relationship with an AI.

**Typical Workflow:**

1. **Session Start:** The AI agent is initialized. Its first instruction is to read `master_instructions.yaml`. Following the rules within, it creates an editable in-session copy of the instructions.  
2. **Collaborative Session:** The user and AI interact. They might identify a rule that needs changing or a new persona trait to add. For example, the user says, "From now on, I want you to summarize our conversations before ending."  
3. **Programmatic Update:** The AI acknowledges the request and announces its action: "Understood. I will now use `add_item.py` to add this as a new rule to our session instructions." It executes the script via its Code Interpreter, modifying the in-session copy. The previous state of the rules is automatically archived within the data structure.  
4. **Session Conclusion:** At the end of the conversation, the user asks the AI to prepare the final instructions: `"Prepare the instructions for saving."`  
5. **Export & "Commit":** The AI reads the final state of its in-session instructions and presents the complete YAML content in a code block. The user then copies this content, and **manually saves it** as the new `master_instructions.yaml` in the AI's Knowledge space, overwriting the old version.  
6. **Evolution:** The next session starts at Step 1, but with the new, improved instruction set.

#### **5\. Advanced Use Cases**

* **Merging Divergent Histories:** If a user runs multiple chat instances and makes different changes in each, they can use `merge.py` to combine the instruction sets. The AI will facilitate this by identifying non-conflicting changes and presenting any direct conflicts to the user for a final decision.  
* **System Maintenance:** If the `master_instructions.yaml` file becomes too large due to its internal history, the user can instruct the AI to use `prune.py` to clean out old, archived versions of keys.

