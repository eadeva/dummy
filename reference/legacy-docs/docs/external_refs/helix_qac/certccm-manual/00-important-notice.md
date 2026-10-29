# Important Notice

Important Notice
Change of Company Ownership
Programming Research Ltd., also known as “PRQA”, became a wholly owned subsidiary of Perforce Software Inc., also
known as “Perforce”, in May 2018.
Disclaimer of Warranty
This document should only be used in conjunction with CERTCCM.
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
Source of Rules
6
CERT C Rules and Recommendations
6
Enforcement of CERT C by Helix QAC for C
7
2 | Installation
8
Windows Installation
8
Linux Installation
8
3 | CERTCCM Components
9
Dataflow
9
4 | Guideline Enforcement
10
CSV Rule Summary
10
Preprocessor (PRE)
10
Rule
10
Recommendation
11
Declarations and Initialization (DCL)
12
Rule
12
Recommendation
13
Expressions (EXP)
15
Rule
15
Recommendation
17
Integers (INT)
19
Rule
19
Recommendation
20
Floating Point (FLP)
21
Rule
21
Recommendation
22
Arrays (ARR)
22
Page 3


---
*Page 3*

Rule
22
Recommendation
23
Characters and Strings (STR)
24
Rule
24
Recommendation
25
Memory Management (MEM)
26
Rule
26
Recommendation
26
Input Output (FIO)
27
Rule
27
Recommendation
28
Environment (ENV)
29
Rule
29
Recommendation
30
Signals (SIG)
30
Rule
30
Recommendation
31
Error Handling (ERR)
31
Rule
31
Concurrency (CON)
32
Rule
32
Miscellaneous (MSC)
34
Rule
34
Recommendation
35
POSIX (POS)
37
Optional Rule
37
Rule Enforcement Summary
39
A | Program Return Codes
40
B | Configuration Options
41
-echo,-e
41
-forgetall,-forget,-f
41
-help,-h
41
-namerulefile,-nrf
42
-nomsg,-no,-n
42
Page 4


---
*Page 4*

-only,-o
42
-outputpath,-op
43
-prodoption,-paloption,-qacppoption,-qo,-po
43
-quiet,-q
43
-quietextended,-qx
44
-remark,-rem
44
-settings,-set
45
-url
45
-version,-ver,-v
45
-via
45
-virtualmemorylimit,-vml
46
Page 5


---
*Page 5*
