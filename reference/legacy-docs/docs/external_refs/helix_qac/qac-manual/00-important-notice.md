# Important Notice

Important Notice
Change of Company Ownership
Programming Research Ltd., also known as “PRQA”, became a wholly owned subsidiary of Perforce Software Inc., also
known as “Perforce”, in May 2018.
Disclaimer of Warranty
This document should only be used in conjunction with Helix QAC for C.
Programming Research Ltd have taken due care in preparing this document which it has endeavored to ensure is
accurate at the time of printing. However, no liability can be accepted for errors or omissions; nor should the document
be considered as an expressed or implied warranty of accuracy or completeness, fitness for a particular purpose, or that
the products described perform as specified within.
Copyright Notice
All rights reserved. No part of this document may be reproduced, stored in a retrieval system of any nature, or transmitted
in any form or by any means, including photocopying and recording, without the prior written permission of Programming
Research Ltd., the copyright owner. If any unauthorized acts are carried out in relation to this copyrighted work, a civil
claim for damages may be made and/or a criminal prosecution may result. Copyright ©Programming Research Ltd 2024.
Trademarks
Helix QAC, the Helix QAC logo, Helix QAC for C, Helix QAC for C++ and High Integrity C++ (HIC++) are trademarks of
Programming Research Ltd.
"MISRA", "MISRA C" and "MISRA C++" are registered trademarks of The MISRA Consortium Limited.
"AUTOSAR" is a registered trademark of AUTOSAR GbR, held on behalf of the AUTOSAR Development Partnership.
"CERT" is a registered trademark of Carnegie Mellon University.
Yices is a registered trademark of SRI International.
Windows is a registered trademark of Microsoft Corporation.
Page 2


---
*Page 2*

Contacting Programming Research Ltd
For technical support, contact your nearest Programming Research Ltd. authorized distributor or, alternatively, the
Programming Research Ltd head office as follows
by telephone on +44 (0) 1189 771020
by fax on +1 612.688.7455
or by webpage: https://www.perforce.com/support/request-support
Page 3


---
*Page 3*

Contents
Important Notice
2
Change of Company Ownership
2
Disclaimer of Warranty
2
Copyright Notice
2
Trademarks
2
Contacting Programming Research Ltd
3
1 | Helix QAC for C Overview
14
Analysis Overview
14
2 | Helix QAC for C Installation
15
3 | Helix QAC for C Configuration
16
Configuring  Helix QAC for C
16
Compiler Selection
16
Implementation-Defined Types (option-intrinsictype)
17
Compiler Extensions (option-extensions)
18
Extensions Classes
18
Functions with Definitions in Assembler
19
Standard Extensions Defined via Macros (option -sd)
19
#define of extended keyword
19
_ignore
19
Locking the macro replacement list
20
Redefinition of Extended Data Types
21
Operators
21
System Header Files (option -si)
21
Suppress Output (option -quiet)
22
Additional Include Files (option -forceinclude)
22
Type of Analysis
22
Project Header Files (option -i)
24
Dataflow Analysis Settings (options -po df::...)
24
Rules
24
4 | Analyzing Source Code
25
Analysis Output Files
25
Location of Created Files
25
Preprocessed Source
25
Page 4


---
*Page 4*

Diagnostic Suppression
28
Overview
28
Atomics of Diagnostics
28
Code-based Annotations
28
Suppression Syntax
28
Justification Text Examples
30
Additional Constraints
31
Continuous Suppression Syntax
32
Additional Constraints
32
Location Tag Syntax
32
Examples
33
Single Instance Suppression
33
Range Suppression Using Location Tags
33
Range Suppression Using Line Counting
35
Suppression and Header Files
35
Continuous Suppressions
35
Continuous Suppressions and Forceinclude Header Files
38
Suppression with Justification Text
39
Suppressions for macro identifiers
40
Suppress messages on expansion of a named macro
40
Suppress messages in preprocessor conditional blocks, guarded by a named macro
40
Handling of Pragma-based Suppressions
41
Baselines
43
5 | Metrics
44
Metrics Overview
44
Metric Thresholds
44
Threshold Order
45
Function-Based Metrics
45
STAKI Akiyama's Criterion
47
STAVx Average Size of Statement in Function
47
STBAK Number of Backward Jumps
47
STCAL Number of Functions Called from Function
48
STCYC Cyclomatic Complexity
48
STELF Number of Dangling Else-Ifs
50
Page 5


---
*Page 5*

STFDN Number of Distinct Operands in Function
50
STFDT Number of Operator Occurrences in Function
51
STFN1 Number of Operator Occurrences in Function
51
STFN2 Number of Operand Occurrences in Function
51
STGTO Number of Goto statements
51
STKDN Knot Density
51
STKNT Knot Count
51
STLCT Number of Local Variables Declared
52
STLIN Number of Code Lines
53
STLOP Number of Logical Operators
53
STM07 Essential Cyclomatic Complexity
54
STM19 Number of Exit Points
55
STM29 Number of Functions Calling this Function
56
STMCC Myer’s Interval
56
STMIF Deepest Level of Nesting
57
STPAR Number of Function Parameters
58
STPBG Residual Bugs (STPTH-based est.)
58
STPDN Path Density
58
STPTH Estimated Static Program Paths
58
NPATH Strict Estimated Static Program Paths
61
STRET Number of Return Points in Function
63
STSTx Number of Statements in Function
64
STSUB Number of Function Calls
65
STUNR Number of Unreachable Statements
67
STUNV Unused or Non-Reused Variables
68
STXLN Number of Executable Lines
69
VOCF Language scope
70
File-Based Metrics
70
COMF Discrete comment to statement density
71
STBME Embedded Programmer Months
71
STBMO Organic Programmer Months
71
STBMS Semi-detached Programmer Months
72
STBUG Residual Bugs token-based estimate
72
STCDN Comment to Code Ratio
72
Page 6


---
*Page 6*

STDEV Estimated Development (programmer-days)
73
STDIF Program Difficulty
73
STECT Number of External Variables Declared
73
STEFF Program Effort
73
STFCO Estimated Function Coupling
73
STFNC Number of Functions in File
74
STHAL Halstead Prediction of STTOT
74
STM20 Number of Operand Occurrences
74
STM21 Number of Operator Occurrences
75
STM22 Number of Statements
76
STM28 Number of Non-Header Comments
77
STM33 Number of Internal Comments
77
STOPN Number of Distinct Operands
78
STOPT Number of Distinct Operators
79
STSCT Number of Static Variables Declared
80
STSHN Shannon Information Content
81
STTDE Embedded Total Months
81
STTDO Organic Total Months
81
STTDS Semi-detached Total Months
81
STTLN Total Preprocessed Source Lines
81
STTOT Total Number of Tokens Used
81
STTPP Total Unpreprocessed Code Lines
81
STVAR Total Number of Variables
81
STVOL Program Volume
82
STZIP Zipf Prediction of STTOT
82
6 | Essential Types
83
Introduction
83
MISRA C
83
The Essential Type Concept
83
Composite Expression
83
The Standard Type System
83
ISO C99 Types
83
Terminology
84
Rank
85
Page 7


---
*Page 7*

Anomalies
86
Diagnostic Requirements
86
Essential Type
88
Essential Type Overview
88
Essential Type Category
88
Essential Type
88
Essential Type Principles
89
Essential Type Definitions
89
STLR and UTLR
89
The Essential Type of a Bit-field
89
The Essential Type of a Literal Constant
89
Integer Constants
90
enum Constants
90
Character Constants
90
Boolean Constants
90
The Essential Type of an Arithmetic Expression
90
Composite Expressions
92
Terminology
92
Composite Operators
92
Composite Expressions
93
Essential Type Messages
93
Overview
93
The -strictrank Option
93
Expression Type Usage Messages
94
Assigning Type Conversion Messages
104
Assigning a Constant
105
Assigning a Constant Expression
106
Assigning a Non-Constant Expression
106
Assigning Messages
107
Balancing Type Conversion Messages
113
Integer  / Float Conversions
113
Signed / Unsigned Conversions
114
Operands of Different ETC in a Relational Operation
117
Operands of Different ETC in an Equality or Conditional Operation
117
Page 8


---
*Page 8*

Switch Case Type Conversion Messages
117
Cast Operation Messages
119
Bitwise ~ and << Messages
121
Composite Expression Messages
123
7 | Dataflow
125
8 | Advanced Usage
126
Code Replacement
126
Code Replacement Configuration Option
126
Regular Expression Syntax
126
A | Dataflow Messages
128
Dataflow Messages
128
B | Metric Output File
156
Overview
156
Using the lua API
156
Release Compatibility
156
Architecture of the API
156
Application Programming
156
Running a lua script
156
Additional Script Paths
157
Directory used for output files when using -file
157
Additional _file variables
157
Output Encoding
157
Example lua script
157
Return Codes
158
Table Overviews
158
Global Members and APIs
158
Filename Record
159
Translation Unit (tu) / Project Record (project)
159
Location Record
160
Control Graph Record
160
Type Record
160
Define Record
160
Literal Record
161
Metric Value Record
162
Page 9


---
*Page 9*

Function Metrics
162
Translation Unit / Project Metrics
164
Pragma Record
166
Relationship Record
166
Calls Relationship (<R>C)
166
Include Relationship Subject
166
Include Relationship (<R>I)
167
Value Member Relationship (<R>V)
167
Pointer Member Relationship (<R>P)
167
Extern Variable Initialization (<EXTV>)
167
Refers Relationship (<R>X)
167
Usage Relationship (<R>U)
168
Symbol Record
168
Availability of Records
170
C | Configuration Options
172
-align,-a
172
-alwayssearchincludedirectoriesfirst,-asidf
173
-arithrsh,-ar
174
-prodoption async::safe_functions
174
-bitsigned,-bits
174
-c17inttypedenumerators,-c17intenum
175
-c23auto,-c23a
177
-c23constexpr,-c23cx
178
-c90nolonglongliterals,-c90noll
179
-coderegex,-cre
180
-comment,-co
181
-prodoption comment::dynamic_statistics
182
-d
183
-prodoption development::scaling
185
-prodoption df::analyse_header_functions
186
-prodoption df::function_timeout
186
-prodoption df::struct_last_array_member_size_1
186
-prodoption df::variant_unions
187
-prodoption digit_separator::binary_group
187
Page 10


---
*Page 10*

-prodoption digit_separator::decimal_group
187
-prodoption digit_separator::floating_group
188
-prodoption digit_separator::fractional_group
189
-prodoption digit_separator::hex_group
190
-prodoption digit_separator::non_separated_max_size
191
-prodoption digit_separator::octal_group
192
-echo,-e
193
-enabledataflow,-ed
193
-encoding,-en
193
-errnosettingfunction,-esf
194
-errorstatusreturningfunction,-erf
195
-extensions,-ex
197
-foldplainchar,-fpc
197
-forceinclude,-fi
198
-forgetall,-forget,-f
198
-prodoption format::printf
199
-prodoption format::scanf
200
-prodoption general::trigger_lines
201
-help,-h
201
-hidemacrowarnings,-hmw
202
-prodoption ignore_modification::forceinclude
202
-prodoption ignore_modification::systemdefine
204
-i
205
-indentlevel,-il
205
-intrinsictype,-it
205
-k+r
206
-list
207
-maxerrors,-maxerr
207
-maxlinelength,-mll
208
-maxmacrohistory,-maxmh
208
-prodoption metrics::no_do_while
209
-namelength,-na
210
-namerulefile,-nrf
210
-nomsg,-no,-n
211
Page 11


---
*Page 11*

-only,-o
211
-outputpath,-op
212
-ppfilename,-ppf
212
-pplist,-ppl
212
-ppmetrics,-ppm
212
-pponly,-ppo
213
-prepronamelength,-ppna
213
-prodoption,-paloption,-qacppoption,-qo,-po
214
-prodoption qax::limit
214
-quiet,-q
214
-quietextended,-qx
215
-randomnumbergeneratorseed,-rngs
215
-remark,-rem
217
-rememberfirstdefinedirective,-remfdd
217
-settings,-set
218
-size,-s
219
-skippragma,-spragma
219
-slashwhite,-sl
220
-stoponerror,-soe
221
-strictrank,-sr
221
-strictsignedness,-ss
221
-style,-sty
222
-systemdefine,-sd
223
-systeminclude,-si
223
-tabstop,-tab,-t
223
-thirdparty,-tp
223
-threshold,-thresh
224
-undef
224
-unsignedchar,-u
225
-url
225
-version,-ver,-v
226
-via
226
-virtualmemorylimit,-vml
226
-warncall,-wc
226
Page 12


---
*Page 12*

-warnmacroexpansion,-wme
227
-warnset,-ws
227
-xcase,-xc
231
-xnamelength,-xn
231
D | Helix QAC for C Message Categories
233
E | Messages Terminating Dataflow Analysis
234
F | Program Return Codes
237
G | Default Rules for Helix QAC for C
238
The Default Critical Rule Configuration File
238
0: Warning Information
238
1:  Obsolete Messages
239
2: Minor
239
3: Major
239
4: Local Standards
239
5: Dataflow Analysis
240
6: Portability
240
7: Undefined Behavior
240
8: Language Constraints
240
9: Errors
240
Page 13


---
*Page 13*
