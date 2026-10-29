# 4 | Analyzing Source Code

4 | Analyzing Source Code
There are two types of analysis available: file-based analysis; and Cross-Module Analysis (run via the RCMA
component). File-based analysis results must be available in order for the project-based RCMA to work.
File-based analysis is run on translation units independently. It can be run on one file, a group of files, or all files in the
project. Each file is analyzed with all analysis components in the toolchain for the specific source language of the file.
Note:
A translation unit is a source file together with all headers and source files included via the preprocessing
directive #include, but excluding any source lines skipped by any of the conditional inclusion
preprocessing directives. (The conditional inclusion preprocessing directives (#if, #ifdef,
#ifndef, #elif, #else and #endif) are used to control whether subsequent sections of code
should be ’included’ or ’skipped’.)
During an analysis in Helix QAC, the dialog box will display the process and give you two options: Stop or Abort:
n The Stop command allows Helix QAC to finish processing the current tasks. However, no further source files will
be analyzed.
n The Abort command immediately quits all current analysis and no further source files are analyzed. This
command is useful if you require a quick exit or if the Stop command is taking too long to complete.
Analysis Output Files
During analysis, Helix QAC for C++ produces three forms of output:
n Diagnostic output.
n Metric output1
n Optional preprocessed output.
Diagnostic output is sent to the Helix QAC database, output for metrics to an .arc and preprocessed source to a .i file.
Generated output files have the same name as the source file but with the addition of further file extensions. For
example, the .arc file for source.c will be named source.c.arc and the .i file will be source.c.i.
For information on diagnostic output and the database see the Diagnostic Database section of the Helix QAC user
manual.
Location of Created Files
If you are using either QA·GUI or QA·CLI, then the output locations are automatically set when projects are analyzed.
The database, .arc, and .i files are all located within the ’output’ directory of the relevant project configuration within
the /prqa/configs folder structure.
Preprocessed Source
At times it can be difficult to track the origin of an error or warning, especially for source code that makes heavy use of the
preprocessor. For such code, analyzing the preprocessed source code can help when investigating warnings generated
in the expansion of macros.
1Including semantic information such as: declarations, function call trees, exceptions thrown. This information is used by
Secondary Analysis and Cross-Module Analysis tools.
Page 28


---
*Page 28*

The .i file is created when Generate Preprocessed Source for Analyzed Files is selected in the Helix QAC GUI, see the
Files Panel section in the Helix QAC user manual for information on how to enable this option.
To provide traceability between the preprocessed output and original source code, Helix QAC for C++ also provides the -
ppfilename,-ppf option. When this option is enabled, Helix QAC for C++ will include the source filename and line number
in the generated preprocessed output, for example:
Original source code:
#include "demo.h" int step1(int x)
{
int r = 0;
if (glob > 10)
{
        r = x * x;
}
return(r);
}
Preprocessed code without comments (-ppfilename-):
extern int glob; extern int step1(int x);
extern int lesser(int y);
int step1 ( int x )
{
int r = 0 ;
if ( glob > 10 )
{
    r = x * x ;
}
return ( r ) ;
}
Preprocessed code with comments (-ppfilename+):
Page 29


---
*Page 29*

/*
 *demo.h
 */
/*1 */ extern int glob;
/*2 */ extern int step1(int x);
/*3 */ extern int lesser(int y);
/*
 *prep.c
 */
/*2 */ int step1 ( int x )
/*3 */ {
/*4 */ int r = 0 ;
/*5 */ if ( glob > 10 )
/*6 */ {
/*7 */ r = x * x ;
/*8 */ }
/*9 */ return ( r ) ;
/*10 */ }
Note:
Helix QAC for C++ does not parse function bodies defined in suppressed headers (see Suppress Output
(option -quiet). It is possible, therefore, that, when analyzing a preprocessed file, previously unseen
errors will be generated in function bodies from compiler headers or from third party libraries. The errors
can either just be ignored or the function bodies can be manually removed.
Diagnostic Suppression
Overview
Diagnostics can be suppressed both from the command line and using annotations directly in the source code. For more
information on suppressing output on the command line see Suppress Output (option -quiet).
Page 30


---
*Page 30*

Helix QAC for C++ provides a powerful comment-based annotation syntax that can be used to specify that messages are
to be suppressed at targeted source code locations. The generation of diagnostics is not affected directly by these
suppressions: instead, Helix QAC for C++ stores suppression information in parallel with the diagnostics. This approach
means that suppressions added using comment-based annotations apply to diagnostics generated by all tools in the
analysis tool chain.
Note:
QA_ERROR diagnostics cannot be suppressed by either mechanism as these messages affect the
quality and scope of analysis. Analysis results cannot be trusted until all diagnostics with QA_ERROR
status have been rectified.
Atomics of Diagnostics
All diagnostic messages have as basic information the message number and location. The concept of a location is the
minimum information required to describe the code context to which a message is referring. Currently this information is
a data tuple:
<file,line,column>
This is all that is required to identify any location in source code.
While diagnostics are assigned to a column within the line, suppression annotations always apply to whole lines. That is,
if message 1234 is suppressed for line 37, this will affect all diagnostics for message 1234 on line 37, regardless of the
column of the diagnostic.
Code-based Annotations
Code-based annotations are used to define locations and suppressions. Location tags are used to mark the end of a
suppression defined previously.
Suppressions can apply either to messages emitted from all source origins, or only to messages which originate from the
expansion of a specific macro.
All annotations are written in comments and must be prefixed with the string "PRQA".
Suppression Syntax
The syntax for suppression annotations can use either or both of the following styles of comment:
n A C++ style comment using the following syntax:
// PRQA S[:["]tag_name["]] msg_spec [loc_spec] [# justification]
// PRQA MS ["]macro_name["] [:["]tag_name["]] msg_spec [loc_spec] [#
justification]
// PRQA GS ["]macro_name["] [:["]tag_name["]] msg_spec [!] [# justification]
n A C style comment using the following syntax:
Page 31


---
*Page 31*

/* PRQA S[:["]tag_name["]] msg_spec [loc_spec] [# justification] */
/* PRQA MS ["]macro_name["] [:["]tag_name["]] msg_spec [loc_spec] [#
justification] */
/* PRQA GS ["]macro_name["] [:["]tag_name["]] msg_spec [!] [# justification]
*/
The different suppression annotation kinds operate as follows:
n 'S' annotations apply to messages emitted from all source origins.
n 'MS' annotations apply only to messages which originate from an expansion of the macro named by macro_
name.
n 'GS' annotations apply in preprocessor blocks guarded by the specified macro_name.
The syntax arguments can be defined as follows:
macro_name
is the name of the macro which will cause the listed messages to be suppressed, if they originate
from an expansion of it (at any "level" of macro nesting).
The macro name may optionally be enclosed in quotes. Only one macro name may be specified,
but additional annotations can apply suppressions to the same message set specifying other
macro names.
When specified without the loc_spec the suppression applies to all expansions of the macro in
the translation unit. This is only used with suppression annotations that begin with "MS".
tag_name
is an optional tag that can be used externally to refer to this suppression, for example an external
deviation management system. In the simple case, the tag should start with a letter and not
include spaces. Complex tag names can be specified by surrounding them in quotes.
msg_spec
represents the set of messages to which this suppression should apply. The messages can be a
comma-separated list of message numbers, a range such as 567-575, or a combination of the
two. If all messages are to be suppressed, the predefined name ALL can be used.
For header files shared between C and C++, messages specifiers can be grouped in a product
specifier that specifies that only the messages for the specified product are to be suppressed:
QACPP(1234),QAC(567-575).
loc_spec
is either a location tag representing the end of the suppression range, or a positive number of
physical lines. If a positive number n is used, the suppression will be applied to the line of the
comment and the n following lines. If the suppression is to be applied to the end of the current
file, the predefined name EOF can be used.
Page 32


---
*Page 32*

!
specifies that the suppression should apply for a preprocessor conditional block where macro_
name is not defined. For example, the true group of #if ! defined (macro_name) or the
false group in the #else block of #if defined (macro_name).
Note:
Suppressions only apply for preprocessor groups that appear after the first
preprocessor conditional that references the macro.
#
is the delimiter used to indicate the start of the optional justification text..
justification
is any text justifying a suppression annotation. The justification text will be shown in the
Suppression Report (SUR) or can be accessed using the QACLI ’view’ subcommand. See the
Helix QAC manual for more information on how to generate reports or use QACLI.
To create the justification, Helix QAC for C++ takes the text immediately following the "#"
delimiter, and then:
n for an annotation in a C-style comment, takes the text up to the end-of-line (/*
PRQA S 1234 EOF # Justification1World */Justification text is taken from "#" up
to the end-of-line, that is to say "Justification1".) or the end of comment marker
"*/" (/* PRQA S 1234 EOF # Justification2 // World */Justification text is taken
from "#" up to the "*/", inclusive of the line comment, that is to say:
"Justification2 // World".);
n for an annotation in a C++-style comment, takes the text up to the end-of-line (
and ), or the start of another C++-style comment ( and Justification Text
Examples).
Any whitespace after the "#" and before the "end delimiter" will be removed.
Justification Text Examples
Example 1
/* PRQA S 1234 EOF # Justification1
World */
Justification text is taken from "#" up to the end-of-line, that is to say "Justification1".
Example 2
/* PRQA S 1234 EOF # Justification2 // World */
Justification text is taken from "#" up to the "*/", inclusive of the line comment, that is to say: "Justification2 //
World".
Page 33


---
*Page 33*

Example 3
// PRQA S 1234 EOF # Justification3 // of Static Analyzers
Justification text is taken from "#" up to the end-of-line, that is to say "Justification3".
Example 4
// PRQA S 1234 EOF # Justification4 // World // of Static Analyzers
Justification text is taken from "#" up to the start of the next C99 style comment, that is to say "Justification4".
Example 5
// PRQA S 1234 EOF # Justification5 /* World */
Justification text is taken from "#" up to the end-of-line, inclusive of the C-style comment, that is to say
"Justification5 /* World */"
Example 6
// PRQA S 1234 EOF ### Justification6
Justification text is taken from "#" up to the end-of-line, that is to say "Justification6".
Example 7
// PRQA S 1234 EOF # Justification7 // PRQA S 1234 EOF
Justification text is taken from "#" up to the start of the next line comment, that is to say "Justification7".
Additional Constraints
1. A suppression annotation without a loc_spec refers to the current line only.
2. Where loc_spec is a location tag, the suppression applies from the current line until the first location tag
appearing in the current file. Refer to Location Tag Syntax.
Note:
Problems with annotations will be highlighted by diagnostics in the range 4810-4840.
Page 34


---
*Page 34*

Continuous Suppression Syntax
Continuous suppression annotations allow for both a disabling statement and a re-enabling statement. The disabling
statement will suppress messages from that line on. A reenabling statement will remove the suppression from the line of
the re-enabling statement onwards, so that the message will no longer be suppressed.
The syntax for continuous suppressions is:
// PRQA S msg_spec [++|--]
where:
msg_spec
is the same as for explicit suppressions (refer to Suppression Syntax).
++
specifies that this is a disabling statement. The set of messages in msg_spec are to be suppressed from this line
onwards.
--
specifies that this is a re-enabling statement. For any message in msg_spec that was previously suppressed
through a disabling statement, that message is no longer to be suppressed from the current line onwards.
Additional Constraints
1. Continuous suppressions do not change the effects of other forms of suppression annotations.
2. A disabled product specific message will only be enabled by an enabling suppression that includes the same
product specifier as the disabling suppression.
3. A disabling continuous suppression (++) in a -forceinclude header file is modeled as if it had been specified
on the first line of the main source file. The suppression does not apply to any -forceinclude header files.
4. An enabling continuous suppression (--) in a -forceinclude header file has no effect and will be ignored.
Problems with annotations will be highlighted by diagnostics in the range 4810-4840.
Location Tag Syntax
The syntax for location tags is:
// PRQA L:tag_name
where tag_name is a name used in a previous suppression annotation that refers to this location.
Example usage:
// PRQA L:end_of_MyStruct
Effects: Creates a location tag at the current line, end_of_MyStruct, that can be referenced by a previous
suppression annotation. In this example, the location tag would be positioned at the line after the struct definition ends. A
suppression annotation before the struct definition that references the end_of_MyStruct location will result in the
suppression of messages for the whole struct.
The line of the location annotation is included in the range of lines suppressed by the suppression annotation.
Page 35


---
*Page 35*

Examples
The aim of this section is to provide examples of suppression in various use cases, covering code annotations and the
resulting effect.
Single Instance Suppression
Simple suppression of one message on the current line
Line 29
Line 30
doSomething(a, b); // PRQA S 1234
Line 31
Effects: All instances of message 1234 will be suppressed on the line 30.
Note:
The following will not result in a suppression, as the suppression statement applies to line 29, and not line
30:
Line 29 // PRQA S 1234
Line 30 doSomething(a, b);
Line 31
To put the suppression on a line before the diagnostic, use a range suppression.
Range Suppression Using Location Tags
Suppress between current line and tag
Line 10
Line 11
// PRQA S 1234 end_of_MyStruct
Line 12
struct MyStruct {
...
Line 72
Line 73
}; // end of struct definition
Line 74
// PRQA L:end_of_MyStruct       
Effects: Message 1234 suppressed for lines 10-74 inclusive. This covers the whole struct definition.
Page 36


---
*Page 36*

Suppress between current line and end of file
Line 1
Line 2
Line 3
// PRQA S 1234 EOF
Line 4
...
Effects: Message 1234 suppressed between line 3 and the end of the file.
Suppress ALL messages
Line 29
Line 30 doSomething(a, b); // PRQA S ALL
Line 31
Effects: All messages suppressed on line 30.
Suppress Messages for a specific product
Line 01 #if defined (__cplusplus)
Line 02 extern "C" {
Line 03 #endif
Line 29
Line 30 doSomething(a, b); // PRQA S QACPP(1234),QAC(2500-2600)
Line 31
Line 50 #if defined (__cplusplus)
Line 51 }
Line 52 #endif
Effects: Suppresses Helix QAC for C++ message 1234 and Helix QAC for C messages 2500 to 2600 on line 30.
Page 37


---
*Page 37*

Range Suppression Using Line Counting
For the next ’n’ lines inclusive
Line 29
// PRQA S 1234 1
Line 30 doSomething(a, b);
Line 31 calculate(x, y);
Effects: Message 1234 suppressed for lines 29 and 30. This affects the doSomething() call, but not the calculate
() call.
Suppression and Header Files
Range suppression in and around a header file
// foo.h     
Line 29 // PRQA S 1234 EOF
Line 30 doSomething(a, b);
Line 31
//foo.cc    
Line 10 // PRQA S 4321 1
Line 11 #include "foo.h"
Effects: Message 1234 is suppressed from line 29 to the end of the header file foo.h. Message 4321 is suppressed on
line 10 and 11 of foo.cc and for foo.h in its entirety.
Continuous Suppressions
Simple on/off continuous suppression
Line 10
// PRQA S 1234 ++
Line 11
Line 73
Line 74 // PRQA S 1234 --
Effects: Message 1234 suppressed between lines 10 and 74 inclusive.
Page 38


---
*Page 38*

Continuous suppression for all messages
Line 10 // PRQA S ALL ++
Line 11 // generated code starts here
...
Line 73 // generated code ends here
            Line 74 // PRQA S ALL --
Effects: All messages are suppressed between lines 10 and 74, i.e. for the range of the generated code.
Continuous suppression with selective re-enabling
Line 10
// PRQA S ALL ++
Line 11
// PRQA S 1234,1236-1238, 1240 --
...
(no other annotations)
Effects: All messages are suppressed on line 10. From line 11 through the whole file all messages are suppressed
except for 1234, 1236, 1237, 1238 and 1240.
Combinations of continuous suppressions
Line 10 // PRQA S 1234-1240 ++
Line 11
...
Line 73
Line 74 // PRQA S 1235 --
...
Line 88 // PRQA S 1238-1240 --
Line 89 // PRQA S 1235 ++
...
(no other annotations)
Page 39


---
*Page 39*

Effects: Message 1234, 1236 and 1237 are suppressed from line 10 onwards. Message 1235 is suppressed between
lines 10 and 73, and from line 89 onwards. Messages 1238, 1239 and 1240 are suppressed between lines 10 and 88.
Continuous suppressions and product specific messages
Line 10 // PRQA S QACPP(1234),QAC(1234) ++                    
...
Line 19
Line 20 calculate(x, y);
Line 21 // PRQA S 1234 --
Line 22 calculate(x, y);
Line 23 // PRQA S QAC(1234) --
Line 24 calculate(x, y);
Line 25 // PRQA S QACPP(1234) --
Line 26 calculate(x, y);
Line 27
...
Effects: Helix QAC for C and Helix QAC for C++ messages 1234 are suppressed from line 10 to 23. The annotation on
line 21 has no impact on the suppression added on line 10. From line 23 onwards Helix QAC for C message 1234 is
enabled. From line 25 onwards Helix QAC for C++ messages 1234 is enabled.
Continuous suppressions and header files
// foo.h
Line 28
Line 29 // PRQA 1234 --
Line 30 doSomething(a, b);
...
// foo.cc
Line 10 // PRQA S 1234 ++        
Page 40


---
*Page 40*

Line 11 #include "foo.h"
...
Line 49
Line 50 calculate(x, y);
Line 51
...
(no other annotations)
Effects: In foo.cc, message 1234 is suppressed from line 10 through to the end of the file. In foo.h, message 1234
suppressed from line 1 to 29. The annotation on line 29 of foo.h has no affect on foo.cc.
Continuous Suppressions and Forceinclude Header Files
// fi.h
Line 29 // PRQA S 1234 ++
Line 30
Line 31 doSomething(a, b);
Line 32
// foo.cc (-fi fi.h)
Line 10
Line 11 doSomething(a, b);
Line 12
...
Line 20 // PRQA S 1234 --
Line 21 calculate(x, y);
Line 22
Effects: Message 1234 is suppressed from line 1 to 20 of foo.cc only. The suppression has no affect on any of the
lines in the force include file. Other forms of suppressions can be used to suppress messages in force include files (see
Range Suppression Using Location Tags).
Page 41


---
*Page 41*

Suppression with Justification Text
Simple suppression of one message with justification text
Line 29
Line 30 doSomething(a, b); // PRQA S 1234 # This is allowed
Line 31
Effects: All instances of message 1234 will be suppressed on line 30 and the justification text "This is allowed" will be
associated with the suppression.
Separate justification text associated with suppressions for different message
Line 29
// PRQA S 1234 1 # This is allowed // PRQA S 1235 1 # Agreed with QA
Line 30
doSomething(a, b);
Line 31
Effects: All instances of message 1234 and 1235 will be suppressed on line 29 and 30 and the justification text "This is
allowed" will be associated with the suppression for 1234, whilst the justification text "Agreed with QA" will be associated
with the suppression for 1235.
Suppressions for macro identifiers
Suppress messages on expansion of a named macro
Line 28
Line 29
// PRQA MS "offsetof" ALL EOF
Line 30
#include <stddef.h>
Line 31
Line 32
struct S {
Line 33
int x, y;
Line 34
};
Line 35  size_t offset_y = offsetof (struct S, y);
Line 36
Effects: All messages originating from the expansion of offsetof (which will have some non-portable library definition
that would probably produce warnings) will be suppressed in this file.
Page 42


---
*Page 42*

Suppress messages in preprocessor conditional blocks, guarded by a named macro
// PRQA GS "DEBUG" ALL
#ifdef DEBUG
void memoryDump() { /* ...  */}
#endif
Effects: All messages from lines 2 to 4 will be suppressed.
// PRQA GS "NDEBUG" ALL !
#if defined NDEBUG
// ...
#else
void memoryDump() { /* ...  */}
#endif
Effects: All messages from lines 4 to 6 will be suppressed.
// PRQA GS "NDEBUG" ALL !
#if defined DEBUG
// ...
#elif defined NDEBUG
// ...
#else
void memoryDump() { /* ...  */}
#endif
Effects: All messages from lines 6 to 8 will be suppressed.
Note:
Messages generated in the preprocessor group guarded by defined DEBUG are not suppressed as the
guard for NDEBUG appears later in the file.
Page 43


---
*Page 43*

Handling of Pragma-based Suppressions
The use of #pragma for suppressing messages was deprecated with the introduction of comment-based annotations. In
Helix QAC for C++ 6.6.0, suppressions specified using the #pragma PRQA_MESSAGES_OFF/ON syntax will be mapped
to an almost equivalent comment-based annotation.
The #pragma PRQA_MESSAGES_OFF/ON syntax has two components:
#pragma <enabling or disabling name> <optional message specifier>
The pragma name is mapped to the continuous suppression enabling/disabling locationspecifier as follows:
n PRQA_MESSAGES_OFF -> ++
n PRQA_MESSAGES_ON -> --
The optional pragma message specifier, when set, is used verbatim in the message specifier of the continuous
suppression. If no message specifier is specified, then the special ALL message-specifier is used.
...
Line 10 #pragma PRQA_MESSAGES_OFF
...
Line 20 #pragma PRQA_MESSAGES_ON 1234
...
Line 50 #pragma PRQA_MESSAGES_ON
The above legacy syntax will result in the following comment-based continuous suppressions:
...
Line 10 // PRQA S ALL ++
...
Line 20 // PRQA S 1234 --
...
Line 50 // PRQA S ALL --
Baselines
Baselines are a form of mass suppression of the messages generated against specific version of the code. Baselining is
particularly useful for hiding messages relating to proven legacy code, where it is the messages generated from
incremental changes to that code that are of interest.
See the Generating a Baseline section in the Helix QAC manual for more information on how to generate a baseline.
Page 44


---
*Page 44*
