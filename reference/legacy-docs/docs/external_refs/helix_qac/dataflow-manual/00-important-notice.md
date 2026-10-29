# Important Notice

Important Notice
Change of Company Ownership
Programming Research Ltd., also known as “PRQA”, became a wholly owned subsidiary of Perforce Software Inc., also
known as “Perforce”, in May 2018.
Disclaimer of Warranty
This document should only be used in conjunction with Dataflow.
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
Contacting Programming Research Ltd
For technical support, contact your nearest Programming Research Ltd. authorized distributor or, alternatively, the
Programming Research Ltd head office as follows
by telephone on +44 (0) 1189 771020
by fax on +1 612.688.7455
or by webpage: https://www.perforce.com/support/request-support
Page 2


---
*Page 2*

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
2
1 | Introduction
6
Terminology
6
Invariant Operations
6
Redundant Operations
6
Control Flow Analysis
6
Initialization Tracking
6
Value Tracking
6
Pointer Attribute Tracking
7
Dataflow Terminology Notes
7
Dataflow Message System
7
Analysis Limitations
8
Diagnostics
8
2 | Message Categories
10
Constant Messages
10
Definite Messages
10
Apparent Messages
12
Suspicious Messages
14
Possible Messages
16
3 | Implementation
18
Solver Technology
18
Variable Interdependency
18
Wraparound and Overflow
18
Variable Tracking
19
Initilization Tracking
20
Value Tracking
20
Pointer Attribute tracking
20
Pointer Aliasing
20
Page 3


---
*Page 3*

Inter-function Analysis
20
Objects of Scalar type
20
Objects of Aggregate Type
20
Objects of Union Type
21
Volatile Objects
21
API Usage Checker
22
Function Arguments
22
Function return Values
23
Modeling Limitations
23
Inter-function Analysis
23
Loops
24
Variables with Unknown Value
24
Pointer Aliasing
25
4 | Dataflow Component Configuration
26
Preparation
26
Inter-function Analysis
26
Inter-TU Analysis
26
Analysis Timeout
27
Deterministic Results
28
5 | QAC and QAC++ Components
30
Activating Dataflow Analysis
30
Dataflow-Dependent Metric Values
30
Analysis Timeout
30
Functions Defined in Header Files
30
Flexible Array Member
31
A | Dataflow Messages
32
Deterministic Results
32
Dataflow Messages
32
B | Program Return Codes
73
C | Configuration Options
74
Dataflow Configuration Option Precedence
74
Primary Options
74
Prod Options
74
-crossmoduleanalysisfile,-cmaf
75
Page 4


---
*Page 4*

-prodoption dataflow::log_function_query_time
75
-prodoption dataflow::threads
76
-prodoption df::branch_model_threshold
76
-prodoption df::cache
77
-prodoption df::cache_file
78
-prodoption df::cma
78
-prodoption df::execution_boundary
78
-prodoption df::fncall_result_checked
79
-prodoption df::function_timeout
81
-prodoption df::inter
82
-prodoption df::mta
82
-prodoption df::query_timeout
83
-prodoption df::query_timeout_message
83
-prodoption df::trust_boundary
83
-echo,-e
84
-forgetall,-forget,-f
84
-intrinsictype,-it
85
-list
85
-newarraycookiesize,-nacs
85
-nomsg,-no,-n
86
-only,-o
86
-outputpath,-op
87
-prodoption,-paloption,-qacppoption,-qo,-po
87
-quiet,-q
87
-quietextended,-qx
88
-remark,-rem
88
-settings,-set
89
-url
89
-version,-ver,-v
89
-via
89
-virtualmemorylimit,-vml
90
Page 5


---
*Page 5*
