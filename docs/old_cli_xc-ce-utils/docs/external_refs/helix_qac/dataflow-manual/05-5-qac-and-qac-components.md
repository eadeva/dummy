# 5 | QAC and QAC++ Components

5 | QAC and QAC++ Components
Activating Dataflow Analysis
The option used to enable dataflow analysis is as follows:
-EnableDataflow+
Dataflow may be activated within the Helix QAC GUI. To access the settings, go to the ’Analyze’ menu and select the
’Dataflow settings...’ item; please see the Helix QAC manual for more details.
Message Sets and EnableDataflow
Messages relating to dataflow issues, see Dataflow Messages, are grouped and numbered according to the kind issue
being analyzed, rather than where or how that analysis is taking place. Therefore, it does not follow that all messages in
the dataflow range are controlled by the "-EnableDataflow" option. When "-EnableDataflow" is disabled, analysis
still takes place as part of 'constant folding' which may result in a diagnostic in this range being issued.
The "-EnableDataflow" option enables full value tracking, including cases where the value of a variable is dependent
on a complex path through the function or interactions with other variables.
Dataflow-Dependent Metric Values
Helix QAC generates a range of function- and file-based metrics. Two of the function-based metrics are computed during
dataflow analysis:
n STRET - Number of function return points
n STUNR - Number of unreachable statements
If dataflow is disabled, these metrics will not appear in the metric output. The same is true for the case when the function
on which the above metrics are based is not analyzed due to dataflow being terminated.
Analysis Timeout
For more information on the -po df::function_timeout=n option, see Analysis Timeout.
Functions Defined in Header Files
Dataflow analysis is not performed on function bodies located within a suppressed header file (see the -quiet,-q option).
Additionally, analysis of functions defined in unsuppressed header files can be controlled using the -prodoption
df::analyse_header_functions option.
The possible values for this option in QAC and QAC++ components are:
inter
Analysis of functions defined in header files, including inlining of called functions. This is the default behavior.
intra
Functions defined in header files will only be inlined when called directly or indirectly from a main source file. This can
be specified if performance issues arise with the use of the default 'inter' value for this option, e.g. for a project that
makes limited use of a header file with many interdependent inline functions, as header functions may be inlined,
even when not called directly or indirectly from a main source file.
For both the inter and intra settings, the amount of code that is inlined is dependent on the value specified to -po df::inter.
Page 30


---
*Page 30*

Flexible Array Member
With Helix QAC for C, if the last member of a struct is an array of one element, the member is treated in a similar way to a
C99 flexible array member, and the upper bound is not checked by Dataflow by default. However, if the following option
is specified, Dataflow will consider the size of this array to be one instead:
-po df::struct_last_array_member_size_1
Page 31


---
*Page 31*
