# 5 | Metrics

5 | Metrics
Metrics Overview
A metric is a measure of some quantifiable attribute of source code. No single metric will provide a comprehensive
indicator of code quality, but each provides a different view of aspects such as complexity, readability, residual bugs, or
testability.
RCMA provides 13 additional metrics, of three types:
n Function-Based Metrics
n Class-Based Metrics
n Project-Based Metrics
Metric values are calculated automatically during the analysis process and are recorded in the .arc file.
Please refer to the Helix QAC for C and Helix QAC for C++ component manuals for more information on metrics.
Metric Thresholds
Most metrics can be directly linked to warning messages. By specifying a metric threshold, any generated metric value
falling outside these limits will result in an analysis warning. Thresholds can be set as part of configuring a coding
standard.
These thresholds can be specified with the -threshold option as a relational expression, in the following format:
-threshold metric op value[:message]
where:
metric
The metric name as it appears in the Metrics chapter of the Helix QAC for C, Helix QAC for C++ or
RCMA Component Manual (as appropriate).
operator
A relational operator (<, <=, ==, >, >=).
value
An integer or a floating point value for which RCMA will generate a warning message if the threshold is
exceeded.
message
The warning message that is generated, as an optional entry. This message number should refer to a
dedicated warning message, specified by the user.
If you do not specify a message number for a threshold, RCMA will issue warning 4700.
For example:
STCYA>30
++ WARNING ++: <=0=(4700) Metric value out of threshold range: function() : STCYA =
35.
Page 13


---
*Page 13*

Threshold Order
During analysis, RCMA will compare metric values against the respective thresholds in the order in which they have
been specified. If the relational expression is TRUE, it will issue a warning and abandon further checks for that metric.
As a result, the order in which threshold options are specified is important. If you want RCMA to issue different warnings
for increasing degrees of severity, you should ensure that your thresholds are specified in decreasing order of severity.
For example:
STCYA>=30:5003
STCYA>=20:5004
STCYA>=10:5005
The above thresholds, in the order given, could be used to enforce three levels of Cyclomatic Complexity. If the metric
value is 35, user-defined warning message 5003 will be generated: if the metric value is 25, warning message 5004 will
be generated: and if the metric value is 15, warning message 5005 will be generated.
Function-Based Metrics
Metric
STM29: Number of Functions calling this Function
STM29: Number of Functions calling this Function
RCMA computes STM29 by examining the entire project call tree and counting the nodes that call the function. Calls
made via function pointers are not counted.
Class-Based Metrics
Metric
STCBO: Coupling to other Classes
STCB1: Coupling to other Classes
STCB2: Coupling to other Classes
STLCM: Lack of Cohesion within a Class
STNOC: Number of Immediate Children
STRFC: Respond for Class
STWMC: Weighted Methods in Class
Note:
Class-based metrics only apply to source code written in C++.
Page 14


---
*Page 14*

STCBO: Coupling to other Classes
RCMA computes STCBO by counting the functions and static objects that a class accesses from other classes.
STCB1: Coupling to other Classes
RCMA computes STCB1 by counting classes using this class and used by this class that are outside of the class and any
of its parent or child classes.
STCB2: Coupling to other Classes
RCMA computes STCB2 by counting classes using this class and used by this class.
STLCM: Lack of Cohesion within a Class
RCMA computes STLCM by creating sets of member objects that are accessed from the class methods. Where one
method calls another, the set is the union of the sets from each method. The value of STLCM is the number of sets.
Copy/Move constructors and assignment operators are not considered when calculating this metric.
STNOC: Number of Immediate Children
RCMA computes STNOC by counting the number of classes where the class appears on the right-hand side of the ’:’ in
the class definition.
STRFC: Respond for Class
RCMA computes STRFC by counting the methods of the class, and all distinct methods that are invoked directly within
the class methods. Inherited methods are counted, but overridden methods are not. Each particular method is counted
once, even if it is called more than once.
STWMC: Weighted Methods in Class
RCMA computes STWMC by summing the STCYC metric for each function defined within the class. The following
member functions are not included when calculating the metric:
n Implicitly declared special member functions, or
n Special members explicitly defined =delete or =default.
Project-Based Metrics
Metric
STCYA: Cyclomatic Complexity across the Project
STNEA: Number of Entry Points across the Project
STNFA: Number of Functions across the Project
STNRA: Number of Recursions across the Project
STNGV: Number of Global Variable Definitions across the Project
Page 15


---
*Page 15*

STCYA: Cyclomatic Complexity across the Project
RCMA computes STCYA as follows:
n = number of functions in the project
STNEA: Number of Entry Points across the Project
RCMA computes STNEA by examining the call graph and counting the number of nodes that have external linkage
which are not called.
STNFA: Number of Functions across the Project
RCMA computes STNFA as follows:
n = number of files in the project
Note:
The STFNC metric is a file-based metric of the number of functions in the file.
STNRA: Number of Recursions across the Project
RCMA computes STNRA by summing the count of directly recursive functions and the count of indirectly recursive
functions. Direct recursion is where a function calls itself. Indirect recursion is where a function calls itself via one or more
intermediate functions.
RCMA performs this analysis by examining the call tree to see if a function appears in each branch more than once.
Each distinct loop back to the calling function is counted once, even if it appears on more than one branch.
STNGV: Number of Global Variable Definitions across the Project
RCMA computes STNGV by counting the total number of definitions of variables with external linkage in a project.
Page 16


---
*Page 16*
