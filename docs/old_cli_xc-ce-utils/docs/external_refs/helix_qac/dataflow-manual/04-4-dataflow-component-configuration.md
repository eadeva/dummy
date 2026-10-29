# 4 | Dataflow Component Configuration

4 | Dataflow Component Configuration
Preparation
Dataflow analysis is intrinsically an intensive and, sometimes, time-consuming process and analysis will usually take
significantly longer if dataflow is enabled. In practice, it cannot be conducted on code which contains certain syntax
errors (QA_ERROR messages) or even, in some cases, constraint errors and it may be aborted for the current function
or even the entire translation unit if such errors are encountered. In these cases one of the following two Dataflow
Recovery messages are generated:
2753: As a result of error message ’%s’, dataflow analysis of the remainder of this function is not possible.
2754: As a result of error message ’%s’, dataflow analysis of the remainder of this translation unit is not possible.
It is therefore wise to ensure that configuration and major coding problems have been addressed in standard Helix QAC
analysis before enabling dataflow analysis.
Dataflow analysis will be most effective when examining code that is well structured. Unstructured code can present
particular analysis difficulties and dataflow analysis of a function will be terminated, for example, when a goto statement
jumping to an earlier label is encountered.
Inter-function Analysis
The depth of inter-function analysis can be adjusted by specifying the following option:
-po df::inter=x
where the value 2*10x specifies the maximum number of simplified statements a called function can contain for it to be
expanded into the caller (See -po df::inter).
A simplified statement refers to an internal deconstruction of source-level statements which includes expansion of
temporaries, deconstruction of compound statements according to sequence points, and other requirements of dataflow
examination. Therefore, the number of explicit statements in a function will nearly always be less than the number of
simple statements.
Additionally, the caller is not allowed to exceed 200,000 simplified statements as a result of inter-function analysis. Thus
a subsequent function call may not be expanded if it would result in the caller exceeding this limit, even if the called
function itself has fewer than 2*10x simplified statements. When x is set to zero, no calls are expanded in analyzed
functions. x can be at most 5, and with this value message 2756 will be issued, whenever a called function cannot be
expanded due to its size.
2756: Could not expand function call to ’%1s’ with maximum ’-po df::inter’ value.
Inter-TU Analysis
Whole program dataflow analysis can be enabled using the following option:
-po df::cma+
When the -po df::cma option is enabled, functions with external linkage from other translation units will be considered for
expansion, for example:
Page 26


---
*Page 26*

// t1.cc
void f1 (int i)
{
1 / i;
/* Definition division by zero. */
}
// t2.cc
extern void f1 (int i);
void f2 ()
{
int i = 0;
f1(i);
/* Called from here */
}
An analysis of t1.cc followed by t2.cc will result in the expansion of f1 into f2. A function from another translation
unit will only be expanded if a previously analyzed definition is available. For example, f1 will not be expanded into f2 if
the order of analysis is t2.cc followed by t1.cc.
Each subsequent analysis run will result in more information being stored for project functions. This should result in a
reduction of the number of Possible issues and a potential increase in the number of Definite, Apparent and Suspicious
issues found.
In order to facilitate the batch running of multiple analysis runs, qacli has been extended to include the option --
inter-tu-dataflow.
Note:
Previously, you needed to specify the --repeat <n> option, but this has been deprecated and
replaced by the --inter-tu-dataflow option. For more information, please refer to the QA·CLI
section of the Helix QAC manual.
Analysis Timeout
Two options have been implemented which provide control over the time allowed for dataflow analysis.
-po df::query_timeout=n
-po df::function_timeout=n
These options are case sensitive and the numeric argument represents a maximum time measured in milliseconds.
Page 27


---
*Page 27*

During the course of dataflow analysis, many queries will typically be submitted to the solver engine. Most queries will be
conducted within the passage of a few milliseconds, but an individual query can sometimes take an excessive amount of
time to reach a conclusion. This may be indicative of some particularly complex code or a difficult sequence of
operations.
The df::query_timeout option allows a time limit to be applied to an individual query. By default this limit is set at 10000
milliseconds (10 seconds). If such a timeout occurs on an individual query, it may result in a false negative, but in
practice, this is unlikely unless the timeout value is substantially reduced. A query which results in a timeout rarely yields
a result of any significance.
The df::function_timeout option applies a time limit to the analysis of an entire function. However checking of the function
timeout limit is never applied until the current query has been completed or has itself timed out. If no function timeout
value is specified, analysis will continue without limit. When a function timeout occurs, message 2755 is generated.
2755: Analysis time of function ’%1s’ has exceeded the configured maximum: ’%2sms’. Dataflow analysis continues with
the next function.
Note:
Dataflow performance is correlated to the number of queries, which is dependent on how much and what
kind of analysis is being performed. Reducing the set of dataflow messages will reduce the number of
queries and so will improve performance.
The df::query_timeout_message option can be enabled if notification of any query timing out is required, with message
2758, regardless of the df::function_timeout configuration.
Note:
If a timeout message persists, then, in addition to the complexity of the code, you may want to check the
usage of your computer’s CPU to see whether other processes are taking up the resources that would
otherwise be used to run dataflow analysis.
As part of analysis by the primary analysis component, configuration options pertinent to dataflow analysis are also
stored. For example, the size and alignment of fundamental types specified by the -size and -align options are
stored for each translation unit.
Note:
The -po df::function_timeout option is used both by the primary analysis component and by the dataflow
component. If specified to the primary analysis component, that value will be stored with the other
configuration options for each translation unit and it will be the value specified to the primary analysis
component that will be used by the dataflow component for functions from that translation unit.
Deterministic Results
The use of timeouts ensures that a given dataflow query never exceeds a fixed amount of time. However, in some
environments, determinism of results may be required. See Analysis Timeout for more information on timeouts.
The time it takes to evaluate a query directly correlates to the performance of the machine running the analysis. A
machine running with 4GHz CPUs and 512GB of RAM will be capable of evaluating queries significantly faster than a
limited machine with a 2GHz CPU with and 6GB of RAM, especially if the Operating System is also swapping processes
to disk.
Page 28


---
*Page 28*

When consistency across different machines and runs is a must, you should enable the -po df::query_timeout_
message option, along with messages 2755, 2757 and 2758. Two separate analysis runs can then be considered
equivalent if the generation of 2755, 2757 and 2758 are the same.
Page 29


---
*Page 29*
