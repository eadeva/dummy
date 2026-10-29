# G | Default Rules for Helix QAC for C

G | Default Rules for Helix QAC for C
Sample sets of rules are provided with  Helix QAC for C. The Default set contains the entire  Helix QAC for C message set,
while the Critical set contains a reduced selection more suited to legacy code. There is no obligation to use these rule
sets, but even if not used, they can provide a starting point for designing a custom rule set.
Rules are organised into a tree structure. The tree is organized into levels and groups. There are 10 levels supplied in the
Default message set for  Helix QAC for C, and within each of these levels there are groups representing an unlimited
further division of message output.
The Default Critical Rule Configuration File
This configuration file shows a reduced set of messages. Messages that are disabled are shown grayed out. This file
picks out the more serious problems, and is particularly suited for use with legacy code.
The C Language groups that are enabled are:
0.1 Annotations
All messages
0.3 Parser Recovery
All messages
0.4 Dataflow Recovery
All messages
2.16 Enumerations
Only message 1317 enabled
3.1 - 3.6 Arithmetic Types
Reduced set
3.7 Functions
Reduced set
3.8 Pointers
All messages enabled
3.9 - 3.11
Reduced set
5 Dataflow
Reduced set
7 Undefined Behavior
Reduced set
8 Language Constraints
Reduced set
9 Errors
All messages
0: Warning Information
These are information level warnings with the lowest level of importance.
Group
Description
Annotations
Syntax problems in annotations (used in code-based  suppressions).
Parsing recovery
Informational  messages generated in the course of recovering from a parsing error.
Dataflow recovery
Informational  messages generated in the course of recovering from an internal dataflow  analysis failure.
Page 238


---
*Page 238*

1:  Obsolete Messages
Messages marked as obsolete are kept for backwards compatibility for 2 product releases, and will be subsequently
removed.
2: Minor
These messages identify issues which may infringe coding standard requirements, but which are not necessarily serious
errors. These message groups are associated with different aspects of the C language.
3: Major
Major messages are those which are likely to identify a significant coding error, anomaly or problem. These messages,
as in 7, 8 and 9, are generally considered too important to ignore without good justification. These message groups are
associated with different aspects of the C language.
4: Local Standards
These messages identify features that do not conform to your programming standard. By convention, when a  Helix QAC
for C Compliance Module is installed, additional message groups are added to Level 4 which will contain the messages
corresponding to specific rules in the coding standard.
Page 239


---
*Page 239*

5: Dataflow Analysis
Messages in this level perform analysis of run-time behavior, identifying problems ranging from serious issues such as
undefined behavior to conditions which are frequently associated with coding and logic errors.
For more information on these messages, refer to the Dataflow manual.
6: Portability
Group
Description
ISO C90 Conformance
Limits
Messages  which identify violations of the translation limits defined in the C90  standard. Code which
exceeds these limits may not be portable to all  conforming C90 implementations.
ISO C99 Conformance
Limits
Messages  which identify violations of the translation limits defined in the C99  standard. Code which
exceeds these limits may not be portable to all  conforming C99 implementations.
Implementation defined
Code constructs which will behave in ways which may  vary between different compilers.
Language extensions
Code  constructs which  Helix QAC for C is able to parse but which do not conform to the C90 or  C99
standards.
ISO C99 Language
features
C99 code constructs that are not part of the C90  language definition.
7: Undefined Behavior
Group
Description
CMA Undefined
Behavior
Constructs  whose behavior is explicitly described as undefined in the language standard  and which
have been identified by using CMA.
Explicitly undefined
Constructs  (not classified as dataflow dependant) whose behavior is explicitly described  as "undefined"
in the language standard.
Implicitly undefined
Constructs  whose behavior is not described in the language standard and whose behavior  is therefore
undefined by implication (only).
8: Language Constraints
These messages identify constructs which violate the language standard.
9: Errors
These errors cannot be suppressed in output. Analysis, if any, produced by  Helix QAC for C will be incomplete and
should not be relied upon.
Group
Description
Helix QAC for C
configuration
Messages  highlighting problems with the configuration passed to the tools.
Syntax errors
Invalid syntax in the source code.
Page 240


---
*Page 240*
