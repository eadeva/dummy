# Important Notice

Important Notice
Change of Company Ownership
Programming Research Ltd., also known as “PRQA”, became a wholly owned subsidiary of Perforce Software Inc., also
known as “Perforce”, in May 2018.
Disclaimer of Warranty
This document should only be used in conjunction with Helix QAC for C++.
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
"MISRA", "MISRA C" and "MISRA C++" are registered trademarks of The MISRA Consortium Limited.
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
1 | Helix QAC for C++ Overview
15
Analysis Overview
15
2 | Helix QAC for C++ Installation
17
Updating of Layout Configuration Files
17
3 | Helix QAC for C++ Configuration
18
Type of Compiler
18
Implementation Defined Types (option -intrinsictype)
20
Standard Extensions
21
Type of Analysis
24
Project Header Files (option -i)
25
Rules
26
4 | Analyzing Source Code
28
Analysis Output Files
28
Location of Created Files
28
Preprocessed Source
28
Diagnostic Suppression
30
Overview
30
Atomics of Diagnostics
31
Code-based Annotations
31
Suppression Syntax
31
Justification Text Examples
33
Additional Constraints
34
Continuous Suppression Syntax
35
Additional Constraints
35
Location Tag Syntax
35
Examples
36
Single Instance Suppression
36
Page 4


---
*Page 4*

Range Suppression Using Location Tags
36
Suppress ALL messages
37
Range Suppression Using Line Counting
38
Suppression and Header Files
38
Continuous Suppressions
38
Simple on/off continuous suppression
38
Continuous suppression for all messages
39
Continuous suppression with selective re-enabling
39
Combinations of continuous suppressions
39
Continuous suppressions and product specific messages
40
Continuous suppressions and header files
40
Continuous Suppressions and Forceinclude Header Files
41
Suppression with Justification Text
42
Simple suppression of one message with justification text
42
Separate justification text associated with suppressions for different message
42
Suppressions for macro identifiers
42
Suppress messages on expansion of a named macro
42
Suppress messages in preprocessor conditional blocks, guarded by a named macro
43
Handling of Pragma-based Suppressions
44
Baselines
44
5 | Metrics
45
Metrics Overview
45
Metric Thresholds
45
Threshold Order
46
Function-Based Metrics
46
STAVx: Average Size of Statement in Function
47
STBAK: Number of Backward Jumps
48
STCAL: Number of Functions Called from Function
49
STCYC: Cyclomatic Complexity
49
STELF: Number of Dangling Else-Ifs
50
STFDN: Number of Distinct Operands in Function
51
STFDT: Number of Distinct Operators in Function
51
STFN1: Number of Operator Occurrences in Function
51
STFN2: Number of Operand Occurrences in Function
52
Page 5


---
*Page 5*

STGTO: Number of Goto statements
52
STKDN: Knot Density
52
STKNT: Knot Count
52
STLCT: Number of Local Variables Declared
53
STLIN: Number of Code Lines
53
STLOP: Number of Logical Operators
54
STM07: Essential Cyclomatic Complexity
55
STM19: Number of Exit Points
56
STM29: Number of Functions Calling this Function
56
STMIF: Deepest Level of Nesting
56
STPAR: Number of Function Parameters
57
STPTH: Estimated Static Program Paths
57
STRET: Number of Return Points in Function
62
STSTx: Number of Statements in Function
62
STSUB: Number of Function Calls
64
STUNR: Number of Unreachable Statements
65
Statement Kind Counted
65
STXLN: Number of Executable Lines
66
File-Based Metrics
67
COMF Discrete comment to statement density
69
STBME Embedded Programmer Months
69
STBMO Organic Programmer Months
69
STBMS Semi-detached Programmer Months
69
STBUG Residual Bugs token-based estimate
69
STCDN Comment to Code Ratio
69
STDEV Estimated Development (programmer-days)
70
STDIF Program Difficulty
70
STECT Number of External Variables Declared
70
STEFF Program Effort
71
STFCO Estimated Function Coupling
71
STFNC Number of Functions in File
71
STHAL Halstead Prediction of STTOT
72
STM20 Number of Operand Occurrences
72
STM21 Number of Operator Occurrences
72
Page 6


---
*Page 6*

STM22 Number of Statements
73
STM28 Number of Non-Header Comments
74
STM33 Number of Internal Comments
74
STOPN Number of Distinct Operands
75
STOPT Number of Distinct Operators
76
STSCT Number of Static Variables Declared
77
STSHN Shannon Information Content
78
STTDE Embedded Total Months
78
STTDO Organic Total Months
78
STTDS Semi-detached Total Months
78
STTLN Total Preprocessed Code Lines
78
STTOT Total Number of Tokens Used
78
STTPP Total Unpreprocessed Code Lines
78
STVAR Total Number of Variables
78
STCCA Total number of characters
79
STCCB Total number of code characters
79
STCCC Total number of comment characters
80
STVOL Program Volume
80
STZIP Zipf Prediction of STTOT
80
VOCF Language scope
80
Class-Based Metrics
80
STDIT Deepest Inheritance
81
STMTH Number of Methods Declared in Class
81
STNOP Number of Immediate Parents
81
6 | Dataflow
82
7 | Advanced Usage
83
Code Replacement
83
Code Replacement Configuration Option
83
Non-ASCII characters:
83
Regular Expression Syntax
83
Layout Configuration Files
84
Modifying Spacing Rules
85
Modeling of the assert macro
87
Reverting to standard preprocessor behavior
87
Page 7


---
*Page 7*

A | Dataflow Messages
89
Dataflow Messages
89
B | Metric Output File
118
Overview
118
Using the lua API
118
Release Compatibility
118
Architecture of the API
118
Application Programming
118
Running a lua script
118
Additional Script Paths
119
Directory used for output files when using -file
119
Additional _file variables
119
Output Encoding
119
Example lua script
119
Return Codes
120
Table Overviews
120
Global Members and APIs
120
Filename Record
121
Translation Unit (tu) / Project Record (project)
121
Location Record
122
Allocation Record
122
Control Graph Record
122
Type Record
122
Define Record
123
Literal Record
123
Metric Value Record
125
Function Metrics
125
Translation Unit / Project Metrics
126
Pragma Record
128
Relationship Record
128
Inheritance Relationship (<R>B)
128
Calls Relationship (<R>C)
129
Include Relationship Subject
129
Include Relationship (<R>I)
129
Page 8


---
*Page 8*

Value Member Relationship (<R>V)
130
Pointer Member Relationship (<R>P)
130
Reference Member Relationship (<R>R)
130
Extern Variable Initialization (<EXTV>)
130
Refers Relationship (<R>X)
130
Usage Relationship (<R>U)
131
Symbol Record
131
Availability of Records
134
C | Configuration Options
135
-align,-a
135
-allowconstconvdeduction,-accd
137
-allowdpdtusingdecltype,-adudt
137
-allowfnptrconvdeduction,-afpcd
138
-allowimplicitconvptrmbr,-aicpm
139
-allowimplicitlangconv,-ailc
140
-allowrefcomparisonforuserdefconvseq,-arcfudcs
142
-allowtempnonconstrefbind,-atncrb
143
-allowtmplargnullptrconv,-atanpc
143
-alwaysusedirectinitializer,-audi
144
-arithrsh,-ar
145
-prodoption assert::no_override
146
-prodoption basic_character_set::ignore
146
-prodoption basic_character_set_comment::ignore
147
-prodoption basic_character_set_string_literal::ignore
148
-prodoption basicchar::set
149
-bitsigned,-bits
149
-prodoption class_usage::max_header_depth
150
-coderegex,-cre
150
-prodoption comment::dynamic_statistics
151
-prodoption conv::allow_bitfield_bool_conv
152
-prodoption conv::allow_cntx_bool_conv
153
-c++03alignment,-c++03align
153
-c++03auto,-c++03a
153
-c++03constexpr,-c++03ce
154
Page 9


---
*Page 9*

-c++03decltype,-c++03dt
155
-c++03exceptionspecification,-c++03es
156
-c++03initializer,-c++03init
157
-c++03linkage,-c++03l
158
-c++03nomove,-c++03nm
159
-c++03nostaticassert,-c++03nsa
160
-c++03nounicodechartypes,-c++03nuct
161
-c++03nouserdefinedliterals,-c++03nudl
161
-c++03nullptr,-c++03np
162
-c++03nullptrconst,-c++03npc
163
-c++03plainolddata,-c++03pod
163
-c++03threadlocal,-c++03tl
164
-c++11autodeduction,-c++11auto
165
-c++11nodigitseparators,-c++11nds
165
-c++11nosizeddeallocation,-c++11nsd
166
-c++14aggregate,-c++14agg
167
-c++14constexpr,-c++14ce
169
-c++14exceptionspecification,-c++14es
171
-c++14noextendedoperatornew,-c++14neon
171
-c++14noguaranteedcopyelision,-c++14ngce
172
-c++14notypefromntadeduction,-c++14ntfnd
173
-c++14noutf8charliteral,-c++14nucl
174
-c++14sequenceorder,-c++14so
175
-c++14trigraphs,-c++14tg
175
-c++17nochar8type,-c++17nc8t
176
-c++17noconcepts,-c++17nc
177
-c++17noexplicitbool,-c++17neb
177
-c++17nothreewaycomparison,-c++17ntwc
178
-d
179
-delayparsefntemplates,-dpft
180
-prodoption df::analyse_header_functions
181
-prodoption df::function_timeout
182
-prodoption df::struct_last_array_member_size_1
182
-prodoption df::variant_unions
182
Page 10


---
*Page 10*

-prodoption digit_separator::binary_group
183
-prodoption digit_separator::decimal_group
183
-prodoption digit_separator::floating_group
184
-prodoption digit_separator::fractional_group
185
-prodoption digit_separator::hex_group
186
-prodoption digit_separator::non_separated_max_size
187
-prodoption digit_separator::octal_group
188
-dontusec99decintlittypes,-duc99dilt
189
-echo,-e
191
-enabledataflow,-ed
191
-encoding,-en
191
-errnosettingfunction,-esf
192
-errorstatusreturningfunction,-erf
193
-forceinclude,-fi
195
-forgetall,-forget,-f
195
-prodoption format::printf
196
-prodoption format::scanf
197
-help,-h
198
-hidemacrowarnings,-hmw
198
-prodoption ignore_modification::forceinclude
199
-prodoption ignore_modification::systemdefine
201
-i
202
-prodoption inline_cost::bin_expr
202
-prodoption inline_cost::builtin_init
202
-prodoption inline_cost::cast_expr
202
-prodoption inline_cost::cond_expr
203
-prodoption inline_cost::conv_expr
203
-prodoption inline_cost::do_stmt
203
-prodoption inline_cost::dyn_cast_expr
203
-prodoption inline_cost::for_stmt
204
-prodoption inline_cost::goto_stmt
204
-prodoption inline_cost::if_stmt
204
-prodoption inline_cost::max
204
-prodoption inline_cost::non_virtual_call
205
Page 11


---
*Page 11*

-prodoption inline_cost::throw_expr
206
-prodoption inline_cost::try_stmt
206
-prodoption inline_cost::uny_expr
206
-prodoption inline_cost::virtual_call
206
-prodoption inline_cost::while_stmt
207
-intrinsictype,-it
207
-introducefriendnames,-ifn
207
-iso646keywords,-iso646kw
208
-layoutfile,-lf
209
-layoutignoreheaders,-lih
210
-layoutindentwidth,-liw
211
-layoutusehangingindent,-luhi
211
-prodoption line::max_length
211
-list
212
-maxerrors,-maxerr
212
-maxmacrohistory,-maxmh
212
-maxrecursivetemplatenestingdepth,-mrtnd
213
-prodoption metrics::no_do_while
214
-namerulefile,-nrf
215
-prodoption namespace::max_depth
215
-nestedcomments,-nc
215
-newarraycookiesize,-nacs
216
-nodigraphmodglobalnamespace,-ndmgns
216
-nomsg,-no,-n
217
-noseparateargexpandedcomma,-nsaec
218
-only,-o
218
-outputpath,-op
219
-prodoption pass_by_value::max_size
219
-ppfilename,-ppf
219
-pplist,-ppl
220
-ppmetrics,-ppm
220
-pponly,-ppo
220
-preproc32bittype,-pp32bt
221
-preproccppkeywords,-ppcppkw
221
Page 12


---
*Page 12*

-prodoption,-paloption,-qacppoption,-qo,-po
222
-propagatetemplateparameters,-ptp
222
-prodoption qax::limit
223
-quiet,-q
224
-quietextended,-qx
224
-randomnumbergeneratorseed,-rngs
225
-remark,-rem
227
-rememberfirstdefinedirective,-remfdd
227
-rvaluerefbind,-rvrb
228
-searchdependentbaseclasses,-sdep
229
-settings,-set
230
-size,-s
231
-slashwhite,-sl
231
-stdisglobal,-sig
231
-stoponerror,-soe
232
-stripemptyvaargcomma,-sevac
233
-prodoption switch::min_cases
233
-systemdefine,-sd
234
-systeminclude,-si
234
-tabstop,-tab,-t
234
-thirdparty,-tp
234
-threshold,-thresh
235
-undef
235
-url
236
-version,-ver,-v
236
-via
236
-virtualmemorylimit,-vml
236
-warncall,-wc
237
-warnkeyword,-wk
237
-warnmacroexpansion,-wme
238
-warnpragma,-wp
238
-warnset,-ws
238
Page 13


---
*Page 13*

D | Program Return Codes
243
E | Default Rules for Helix QAC for C++
244
The Default Rule Configuration File
244
0: Warning Information
244
1: Style Guidelines
244
2: Maintainability
245
3: C++ Language Features
245
4: Local Standards
245
5: Design Problems
245
6: Portability
247
7: Complexity
247
8: ISO Standards
247
9: Errors
248
99: Fatal Errors
248
F | Layout Configuration Glossary
249
Page 14


---
*Page 14*
