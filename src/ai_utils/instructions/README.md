# **agent-continuity-protocol**

A protocol for evolving and persisting core AI instructions across chat sessions.

### **System Overview: The Living Instructions Protocol**

Document Version: 1.0  
Last Updated: Thursday, June 26, 2025 at 11:31 PM EDT

#### **1\. Executive Summary**

The "Living Instructions Protocol" is a system designed to overcome the limitations of static, session-based instructions for AI agents. Its purpose is to create a persistent and evolving set of operational rules, personas, and configurations that can be collaboratively maintained and improved over time by a human user and an AI agent.

The system treats the AI's instructions not as a fixed prompt, but as a version-controlled configuration file. It provides a robust toolchain for the AI to manage, update, and validate this configuration in a safe and structured manner, with the human user acting as the final authority for all changes.

#### **2\. Core Design Philosophy**

* **Collaborative Evolution:** The AI's persona and ruleset are not static; they evolve through conversation and explicit agreement between the user and the AI.  
* **Programmatic Robustness:** All modifications to the instruction set are handled by a dedicated library of Python scripts, ensuring consistency and reliability.  
* **Structured & Validated Data:** All instructions are stored in a structured YAML format and validated against a formal schema, preventing errors from malformed configurations.  
* **Self-Contained History:** The instruction file itself contains a built-in audit trail of changes, providing context for future updates and merges.  
* **Human as Final Authority:** The AI can propose and prepare changes, but the human user performs the final "commit" by saving the updated master file.

#### **3\. System Components**

This protocol is comprised of a data file, a schema, and a library of Python scripts, all intended to reside together in the AI's "Knowledge" space or a shared project repository.

**A. Data & Schema:**

* master\_instructions.yaml: The single source of truth. This file contains the complete, current operational instructions for the AI agent.  
* instructions\_schema.yaml: The "contract" or blueprint. It defines the required structure, data types, and keys for the master\_instructions.yaml file, enabling automated validation.

**B. The Python Toolchain:**

* helpers.py: A shared module containing common functions (e.g., loading/saving YAML, timestamp generation).  
* validate.py: Validates an instruction file against the schema.  
* read\_key.py: Safely reads a specific key from the instructions file.  
* update\_key.py: Updates the value of an existing key, automatically archiving the previous state.  
* add\_item.py: Adds a new item to a list within the instructions.  
* delete\_item.py: Deletes an item from a list by its index.  
* prune.py: Manages file size by trimming the inline history.  
* merge.py: Provides a mechanism to combine two divergent versions of the instruction file.

**C. The Test Suite:**

* test\_\*.sh: A series of automated shell scripts for basic "smoke testing" of each Python tool.

#### **4\. Intended Use & Example Workflow**

1. **Session Start:** The AI agent reads master\_instructions.yaml and creates an editable in-session copy.  
2. **Collaborative Session:** The user and AI agree on a change to the instructions.  
3. **Programmatic Update:** The AI calls the relevant script (e.g., update\_key.py) to modify the in-session copy and archive the previous state.  
4. **Session Conclusion:** The user requests the finalized instructions.  
5. **Export & "Commit":** The AI presents the final YAML content. The user copies this and manually saves it as the new master\_instructions.yaml.  
6. **Evolution:** The next session begins with the new, improved instruction set.

#### **5\. License**

This project is licensed under the MIT License. See the LICENSE file for details.