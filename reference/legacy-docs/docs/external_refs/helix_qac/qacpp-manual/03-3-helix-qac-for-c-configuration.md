# 3 | Helix QAC for C++ Configuration

3 | Helix QAC for C++ Configuration
One of the strengths of Helix QAC for C++ is its high degree of configurability. Configuration options are defined in the
Helix QAC Project Properties GUI, Analysis Configuration Tab. The options can be grouped based on:
n Type of Compiler
n Type of Analysis
Type of Compiler
These options are used by Helix QAC for C++ to match the behavior of your compiler:
Option
Effect
Data Types - Interpretation
-arithrsh
Whether the right shift operator performs an arithmetic shift or a
logical shift.
-bitsigned
Whether plain integer bit-fields are treated as signed or
unsigned int.
-dontusec99decintlittypes
Large unsuffixed integral literals may have ’unsigned long’ type.
-intrinsictype
Specifies how size_t, ptrdiff_t, wchar_t and the
underlying type of enums are modeled by Helix QAC for C++ .
Data Types - Size and Alignment
-align
The alignment of each primitive C++ type
-size
The type sizes (measured in bits) implemented in your compiler
environment
Extensions
-allowconstconvdeduct
Allow template argument deduction to succeed for different cv
qualifiers.
-allowfnptrconvdeduct
Allow pointer to function conversions during template argument
deduction.
-allowimplicitconvptrmbr
Allow implicit conversions to pointer to members.
-allowimplicitlangconv
Language linkage conversions are ranked as an exact match.
-allowtempnonconstrefbind
Allow temporaries to bind to non const references.
-allowtmplargnullptrconv
Allow template argument deduction to succeed for null pointer
conversions.
Page 18


---
*Page 18*

Option
Effect
-alwaysusedirectinitializer
Direct initialization used in place of copy initialization.
-delayparsefntemplates
Function templates are only parsed if they are instantiated.
-forceinclude
Implicitly include the specified file at the beginning of each
translation unit.
-introducefriendnames
Names of friend functions made visible in the enclosing
namespace.
-noseparateargexpandedcomma
Comma in macro expansion not treated as argument separator.
-propagatetemplateparameter
Primary template parameter names are visible in explicit
specializations.
-rememberfirstdefinedirective
MACRO redefinitions do not update the replacement list.
-searchdependentbaseclasses
Names in dependent base classes are visible.
-slashwhite
Ignore whitespace between \ and the end of a line
-stdisglobal
Names declared in namespace std are visible in the global
scope.
-stripemptyvaargcomma
Commas appearing before empty __VA_ARGS__ are implicitly
removed.
ISO Standard Version
-c++03alignment
’alignof’ and ’alignas’ not treated as keywords.
-c++03auto
’auto’ reverts to being a storage class specifier.
-c++03constexpr
’constexpr’ not treated as a keyword.
-c++03decltype
’decltype’ not treated as a keyword.
-c++03exceptionspecification
Use ISO 2003 C++ Standard rules for the exception
specifications of implicit members and operator new.
-c++03initializer
Use ISO 2003 C++ Standard rules for braced initializers.
-c++03linkage
Linkage of entities in unnamed namespaces not implicitly
internal.
-c++03nomove
Special member move constructors/assignment operators
never implicitly declared.
Page 19


---
*Page 19*

Option
Effect
-c++03nouserdefinedliterals
A string literal followed by a suffix not parsed as a user defined
literal.
-c++03nullptr
’nullptr’ not treated as a keyword.
-c++11autodeduction
Use ISO 2011 C++ Standard rules for deducing placeholder
types.
ISO Implementation Defined Behavior
-maxrecursivetemplatenestingdepth
The maximum recursive template nesting depth.
-preproc32bittype
Preprocessor constant evaluation using 32bit type.
-rvaluerefbind
Temporaries of class type are directly bound to const
references.
System Headers
-si
Path to search for system header files
-quiet
Suppress parsing and output for files and/or paths
System Macros
-sd
System Macros which are required by your compiler
Implementation Defined Types (option -intrinsictype)
The ISO C++ Standard does not explicitly specify the underlying types to be used for size_t, ptrdiff_t, wchar_t or enum
types.
The -intrinsictype,-it option controls the way these types are implemented and needs to match your compiler
environment. Any corresponding typedef statements contained in header files (e.g. cstddef, cstdio) must reflect how
Helix QAC for C++ is configured. In case of inconsistency, Helix QAC for C++ will generate a QA_ERROR message.
Examine your header files, if necessary, to determine appropriate settings for these options.
The three macro definitions, PRQA_PTRDIFF_T, PRQA_SIZE_T, and PRQA_WCHAR_T, are implicitly defined to the
type that corresponds to the appropriate -intrinsictype setting.
An -intrinsictype option for wchar_t causes Helix QAC for C++ to model wchar_t as an alias to the specified type and not
as a keyword to the distinct type. The macro PRQA_WCHAR_T is only defined when an -intrinsictype option for wchar_t
is specified.
An -intrinsictype option for enum specifies how the underlying type of an enumeration is determined. After the range of
values of an enumeration has been calculated, the first of the specified types large enough to hold all the enums values
will be selected as the underlying type.
For example:
Page 20


---
*Page 20*

// -intrinsictype enum="signed char, unsigned char"
enum E1 // Underlying type 'signed char'
{
     E1_A = 0,
     E1_A = 10
}; enum E2 // Underlying type 'unsigned char'
{
     E1_A = 0,
     E1_A = 128
};
If none of the explicitly specified types are large enough to store all enumeration values then Helix QAC for C++ will try
the following types in sequence:
1. signed int
2. unsigned int
3. signed long
4. unsigned long
5. signed long long
6. unsigned long long
In the case where a type cannot be found to fit all of the values, ie. an enumeration with a negative value and very large
positive value, then the underlying type will be ’signed long long’.
Standard Extensions
Helix QAC for C++ processes the command line macros in the order they are passed, handling the macros specified with
-d before those specified with -systemdefine,-sd.
#define of extended keyword
Compiler manufacturers frequently introduce additional keywords such as idata, tiny, and xhuge to specify memory
models and to allocate memory data. These keywords are often applied like storage class qualifiers in object
declarations and can be ignored during analysis by introducing a #define statement which defines away the keyword.
Replacement list for ignoring tokens
Using one of the _ignore* macro replacement forms is an instruction to Helix QAC for C++ to ignore not just a keyword
but a sequence of tokens starting with a specified keyword. It specifies a macro definition that handles the keyword in
one of several ways.
Page 21


---
*Page 21*

blah=_ignore
ignores blah and the next token.
eseg=_ignore_semi
ignores eseg and everything up to and including the next semi-
colon. However, any code in parentheses is excluded from the
search, which means that any semi-colons within the parentheses
are not taken into account.
asm=_ignore_paren
ignores asm and the contents of a block delimited by ( ), { } or [ ]
interrupt=_ignore_3
ignores interrupt and the following three tokens.
...=_ignore_
modification
see Locking the macro replacement list
Note:
It is also possible to perform search and replace with a regular expression at character level in a source
file. See Code Replacement
Redefinition of Extended Data Types
Sometimes extended data types are introduced into the language to address memorymapped I/O ports or to perform
efficient bit addressing. These data types can usually be redefined to a standard data type during analysis by introducing
a macro or a typedef. For example, access to special function registers is often provided through data types such as sfr
and sbit.
#define sfr unsigned char
typedef unsigned char sfr
Locking the macro replacement list
It is illegal to redefine a macro to have a different replacement list without undefining the macro first (#undef). The default
behavior of Helix QAC for C++ is to ignore the replacement list of the illegal redefinition.
#define A 1
#define A 2 // Illegal redefinition - ignored
int i = A;// Expands to 1
This behavior simplifies handling of extensions as identifiers can be given safe values at startup, and any subsequent
definitions by a compiler or 3rd party header will be ignored.
Some mainstream compilers, however, use the second replacement list rather than the first. The -
rememberfirstdefinedirective,-remfdd option, when disabled, switches the behavior of Helix QAC for C++ so that it uses
the second replacement list rather than the first.
Page 22


---
*Page 22*

// Options: -rememberfirstdefinedirective
#define A 1
#define A 2 // Illegal redefinition - replacement list updated
int i = A;// Expands to 1             
Unfortunately, this means that a safe value given at startup will be replaced should a definition exist in the compiler or 3rd
party header set. This in turn may result in Helix QAC for C++ being unable to parse the source. To address this, _
ignore_modification can be used to specify that the replacement lists of any macro redefinitions are to be ignored.
// Options: -rememberfirstdefinedirective
#define A 1
#define A _ignore_modification
#define A 2 // Illegal redefinition (but ignored)
int i = A;// Expands to 1        
To simplify the configuration process, by default Helix QAC for C++ will treat macros defined in a -forceinclude,-fi header
or defined using the -systemdefine,-sd configuration option as implicitly also having _ignore_modification.
// Options: -rememberfirstdefinedirective- -fi f1.h
// f1.h
#define A 1
// f1.cc
#define A 2 // Redefinition of A (but ignored)
int i = A;// Expands to 1
This behavior can be further refined using the -prodoption ignore_modification::forceinclude and-prodoption ignore_
modification::systemdefine prodoptions.
Page 23


---
*Page 23*

Additional Include Files (option -forceinclude)
If you want to define typedefs, they will need to be specified within your source code. However, rather than introducing
them directly into your source code or header files, usually it is better to create a special header file and "force-include"
this file during analysis.
The run-time absence of a specified force-include file will generate an appropriate QA_ERROR message. See also -
forceinclude,-fi.
System Header Files (option -si)
The ordering of the parameters is important. Helix QAC for C++ will search the directories specified in the order they are
passed processing the -i option before the -systeminclude,-si.
Suppress Output (option -quiet)
The -quiet,-q option can be used to specify that the output of a single file or all files in a path should be suppressed. Note
that this option applies only to included files and has no effect on the main source file. Suppressing analysis in this way
will have the following impact:
n Bodies of functions and function templates will not be parsed or analyzed in the files.1.
n .arc file output will not be generated for the files.
n Diagnostic output will not be written for the files.2
Unlike for the C language, header files in C++ often contain a significant amount of executable code. Therefore care
should be taken when using the -quiet,-q option as it may result in inter-procedural issues being hidden from view, for
example, a divide by zero for a call to an inline function.
Type of Analysis
Option
Effect
General Processing
-encoding
The character set of source files.
-ppfilename
Show file names and line numbers in the preprocessed file.
Dataflow Analysis
-enabledataflow
Whether the DF^2 dataflow analysis is performed.
-prodoption df::function_timeout
Limit the overall time spent in dataflow analysis for each function.
Metrics
1This can aid parsing of headers that contain extensions or non standard constructs not supported by Helix QAC for C++
2Diagnostics for QA_ERROR messages cannot be suppressed and so they will continue to be generated
Page 24


---
*Page 24*

Option
Effect
-ppmetrics
Include header file information in the calculation of metrics.
-threshold
Output the specified message whenever the threshold for specified metric is
exceeded.
Project Headers
-i
Path to search for header files
Project Macros
-d
Macros which are required by your development environment
-undef
Macros which need to be undefined in your development environment
Style
-layoutfile
Name of layout configuration file to use.
-layoutignoreheaders
Ignore header files when performing layout checking.
-layoutindentwidth
Indent width to use when performing layout checks.
-layoutusehangingindent
Use hanging indent for labels.
-tabstop
Number of spaces represented by a tab character
Construct Warnings
-warncall
Generate the specified message if a call to the specified function is
encountered
-warnkeyword
Generate the specified message if the specified keyword is encountered
-warnmacroexpansion
Generate the specified message if the specified macro is expanded in the
source code
-warnpragma
Generate the specified message if the specified pragma is encountered
-warnset
Generate the specified message if the specified member variable is set. This
also includes the optional ability to require a specific value
Project Header Files (option -i)
The ordering of the parameters is important. Helix QAC for C++ will search the directories specified in the order they are
passed processing the -i option before the -systeminclude,-si.
Page 25


---
*Page 25*

Dataflow Analysis
Deep Flow Dataflow is a sophisticated additional phase of analysis, see the Dataflow section for information on its use
and configuration.
Advanced Configuration
Helix QAC for C++ is intended to be used as the C++ analysis component under Helix QAC as part of the overall
Perforce analysis solution. The following advanced options are supported by Helix QAC for C++ but are intended to be
set exclusively by Helix QAC.
Option
Effect
Information
-help
Print brief help description for the program
-settings
Print current values for all configuration options
-version
Print the version number for the executable
Auxiliary
-echo
Specifies a string which is echoed directly to the console
-forgetall
Reset previous configuration settings for an option
-via
Read configuration options from the specified file
Used by Helix QAC only
-only
Generate only the specified warning messages
-nomsg
Suppress the generation of specified messages
-metrics
Enables or disables the generation of metric output to the .arc file
-outputpath
Location to which i and arc output files are be generated
-pplist
Preprocessed file is generated in the output directory with a .i file extension
-url
The URL of the QAX daemon used to store analysis results
Note:
Manually changing any of -nomsg,-no,-n -only,-o, or -outputpath,-op or using them as operands to -
forgetall,-forget,-f, will result in incorrect or missing analyses.
Rules
Rules are used to categorize messages, and to select which message checks to apply. Rules are organized into a tree
structure. The rules at the bottom of the tree have messages mapped to them.
Page 26


---
*Page 26*

Rules are configured using the Rule Configuration tab of the Helix QAC Project Properties. The configuration settings
are read from, and written to, a Rule Configuration File with extension .rcf. The .rcf files can be copied between
projects to obtain consistent configurations. Please refer to the Rule Configuration chapter of the Helix QAC manual for
more details on the management of .rcf files and rules.
Rules have been designed as a flexible method to categorize messages in a way that is meaningful to a company and its
particular projects. It is possible to use different rules for different projects, or to use the same rules across many
projects. A default .rcf file is provided, which is described in Default Rules for Helix QAC for C++
By default all rules are enabled, but individual rules can easily be disabled. Disabling a rule means that all of its
descendants within the tree are also disabled. Only messages mapped to enabled rules are generated by Helix QAC for
C++ . Disabling is sometimes used if a generic ruleset has been used but certain categories of message are not relevant
for the particular project. Disabling is also used on a more temporary basis, to detect and handle one category of
message at a time.
Page 27


---
*Page 27*
