# E | Default Rules for Helix QAC for C++

E | Default Rules for Helix QAC for C++
Sample sets of rules are provided with Helix QAC for C++ . The Default RCF contains the entire Helix QAC for C++
message set, whilst the Critical version contains a reduced set more suited to legacy code, and the Security version
contains a reduced set intended for users whose immediate concern is security related defects and violations.
There is no obligation to use these rule sets, but even if they are not used, they can provide a starting point for designing
a custom rule set.
Rules are organized into a tree structure, consisting of levels and groups, and within each of these levels there are
groups representing further divisions of message output.
Note:
The features supported by Helix QAC for C++ are continually being updated as the ISO C++ standards
evolve and are in turn incorporated into the tool. Therefore, the phrase "ISO C++ standard" as used in
this section refers to the set of ISO C++ features supported by Helix QAC for C++ 6.6.0 at the time of
release.
The Default Rule Configuration File
There follows an explanation for each level and group in the Default RCF.
0: Warning Information
These contains information messages with the lowest level of importance.
Group
Description
Information Messages
Miscellaneous messages related to the running of the tool.
Context Messages
Additional context sub-messages giving clarification to a primary message.
CMA Information
This is a legacy group that has no Helix QAC for C++ messages associated with it.
Annotations
Syntax problems in annotations (used in code-based suppressions).
Dataflow Recovery
Informational messages generated during the course of recovery from an internal dataflow analysis
failure.
1: Style Guidelines
These messages identify contraventions of the standards of source layout, declaration, structure and pre-processing.
Group
Description
Source Layout
Standards
Code layout, including indentation, spacing and line breaks.
Declaration Standards
Declaration issues, including function interfaces, overloading, default arguments, constness, access
protection, and literal representations.
Page 244


---
*Page 244*

Group
Description
Code Structure
Standards
Various code structure issues, including analysis of switch statements, correct use of blocks, use of
literals, and unstructured statements.
Preprocessor
Standards
Preprocessor issues, including header include guards and good practice, notes on macro usage, and
semantic visibility issues based on macro logic.
2: Maintainability
These messages indicate possible maintenance or readability issues in the source file.
Group
Description
Maintenance Warnings
A large range of maintainability issues within a single TU (Translation Unit). Language coverage
includes declaration, definition, initialization, cast/conversion, side effects, and exception specifications.
CMA Declaration
Standards
This is a legacy group that has no Helix QAC for C++ messages associated with it.
CMA Maintenance
Warnings
This is a legacy group that has no Helix QAC for C++ messages associated with it.
3: C++ Language Features
These messages provide instruction on the most effective use of the C++ language. These features include the
translation of C to C++, the use of C++ libraries, and efficient usage of the language.
Group
Description
C++ Improvements
over C
Advice on better C++ paradigms or coding styles over C alternatives. Focus is on macro usage, use of
unions, exception specification and operation, old-style casts, and use of initializers.
Use Libraries
Warnings related to the use of arrays.
Efficiency Notes
Advice on how to improve efficiency. The group includes warnings on parameter passing, function
inlining, and implicit constructors, destructors and copy constructors.
4: Local Standards
These messages identify features that do not conform to your local, bespoke programming standards.
Group
Description
Local Standards
Placeholder for local coding standards. Items placed here might include messages configured using -
warncall, relating, for example, to the use of keywords, calling of named functions, use of #pragma, and
compliance.
5: Design Problems
These messages identify design problems that could range anywhere from serious issues such as undefined behavior,
to conditions that are frequently associated with coding and logic errors.
Page 245


---
*Page 245*

Group
Description
Conversion to Signed
Conversions to a signed type that is not large enough to represent the expected values.
Conversion to
Unsigned
Conversions to an unsigned type of values that are either negative or too large to be represented.
Shift Operations
Shift operations that have an undefined result, or that result in the loss of non-zero bits.
Overflow and
Wraparound
Operations that result in signed arithmetic overflow (undefined behavior) or unsigned arithmetic
wraparound.
Arrays
Operations on objects of array or pointer type that result in undefined behavior.
Pointers
Comparison or subtraction of pointers that address different objects.
Unset Data
Operations that access uninitialized data.
NULL Pointers
Arithmetic or dereferencing operations on NULL pointers.
Redundancy
Redundant initializations, expressions or assignments, often associated with faulty logic.
Control Flow
Unreachable code, infinite loops or incorrect return statements.
Invariant Operations
Expressions that always evaluate to either True or False, frequently associated with faulty logic.
Serious Problems
A range of issues that are very likely to result in program failure.
Serious Resource
Leaks
A range of issues that are very likely to result in memory leaks.
Serious Exception
Problems
A range of issues that are very likely to result in program failure due to the incorrect use of C++
exceptions.
Behavior Problems
Messages highlighting the misuse of language features or constructs that may result in unexpected
program operation.
Potential Problems
A range of issues that could potentially result in program failure.
Potential Resource
Leaks
A range of issues that could potentially result in memory leaks.
Potential Exception
Problems
A range of issues that could potentially result in program failure due to the incorrect use of C++
exceptions.
Preventative Measures
A range of improvements that could be made to avoid common problems.
Serious Resource
Issues
There are no messages in this category.
Page 246


---
*Page 246*

Group
Description
Serious Threading
Issues
There are no messages in this category.
6: Portability
These messages relate to portability between compilers and platforms.
Group
Description
Portability Problems
Code that results in compilation problems or unexpected behavior between different compilers and
platforms.
ISO C++ ’11 Language
Features
Messages that identify constructs which use legal C++11 code but which may not be accepted in non-
C++11conformant compilers.
Language Extensions
Code constructs that do not conform to the ISO C++ standard but that Helix QAC for C++ interprets as
extensions of known compilers.
Implementation Defined
Code constructs for which the behavior may vary according to the particular compiler.
Inline Functions
Code constructs that may cause a compiler not to inline a function even though it has been defined with
the "inline" keyword.
7: Complexity
These messages identify constructs which could impact the understandability of code.
Group
Description
Complexity Problems
For example, diagnostics representing metric thresholds.
8: ISO Standards
These messages identify constructs that violate the definition of the language given in the C++ standard.
Group
Description
CMA Semantic
Warnings
This is a legacy group that has no Helix QAC for C++ messages associated with it.
Semantic Warnings
Semantic violations of the ISO C++ standard.
Syntax Warnings
Constructs that are syntactically incorrect according to the ISO C++ standard.
Deprecated
Use of constructs that are deprecated in the ISO C++ standard.
Page 247


---
*Page 247*

9: Errors
These messages indicate syntax, semantic, or configuration errors that should have been detected by the compiler.
These errors cannot be suppressed in output, and any analysis generated by Helix QAC for C++ will be incomplete and
unreliable.
Note:
Only compilers that have been fully validated to the C++ standard will detect all errors.
Group
Description
Semantic Errors
Invalid semantic representation of the source code.
Syntax Errors
Invalid syntax in the source code.
Configuration Errors
Messages highlighting problems with the configuration passed to the tool.
Unrecoverable Errors
Messages resulting in some or all of the input source having to be ignored.
99: Fatal Errors
These messages highlight errors that are preventing any form of analysis.
Group
Description
Fatal Errors
Messages indicating invalid code and/or permissions, or other unexpected errors.
Page 248


---
*Page 248*
