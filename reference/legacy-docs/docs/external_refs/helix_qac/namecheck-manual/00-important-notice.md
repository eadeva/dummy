# Important Notice

Important Notice
Change of Company Ownership
Programming Research Ltd., also known as “PRQA”, became a wholly owned subsidiary of Perforce Software Inc., also
known as “Perforce”, in May 2018.
Disclaimer of Warranty
This document should only be used in conjunction with Namecheck.
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
1 | Introduction
6
2 | Configuration Basics
7
3 | Configuration File
8
Rule Format (JSON Syntax)
8
Rule Names
8
Filename
9
Included File
9
Definition
9
Space
9
Scope
10
Linkage
10
Type
10
Flag
11
Pattern
11
Invert
11
Message Number
11
Namespace
12
Define Record
12
Example
15
4 | Perl-Compatible Regular Expressions
17
Matching Characters
17
Matching a Number of Times
17
Anchoring
18
Alternate Matching
18
Escaping Special Characters
18
Configuration File Example
19
Getting Feedback on Errors
19
Page 4


---
*Page 4*

Configuration File
19
JSON Syntax Errors
19
Unknown Name
19
Unknown value
20
Regular Expressions
20
A | Program Return Codes
21
B | Configuration Options
22
-echo,-e
22
-forgetall,-forget,-f
22
-namerulefile,-nrf
22
-nomsg,-no,-n
23
-only,-o
23
-outputpath,-op
24
-prodoption,-paloption,-qacppoption,-qo,-po
24
-prodoption qax::limit
24
-quiet,-q
25
-quietextended,-qx
25
-remark,-rem
26
-settings,-set
26
-url
26
-version,-ver,-v
26
-via
27
-virtualmemorylimit,-vml
27
Page 5


---
*Page 5*
