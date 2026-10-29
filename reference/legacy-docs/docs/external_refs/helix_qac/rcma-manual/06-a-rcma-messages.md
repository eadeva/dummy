# A | RCMA Messages

A | RCMA Messages
Message
ID
Message Text
Language
Multi-
Homed
CMA Declaration Standards
1500
The object '%1s' is declared but is not used within this project.
C\C++
Yes
1501
The function '%1s' is declared but is not used within this project.
C\C++
Yes
1502
The object '%1s' is defined but is not used within this project.
C\C++
No
1503
The function '%1s' is defined but is not used within this project.
C\C++
No
1534
The macro '%1s' is declared but not used within this project.
C\C++
No
1535
The typedef '%1s' is declared but not used within this project.
C\C++
No
1536
The tag '%1s' is declared but not used within this project.
C\C++
No
1752
The object '%1s' with external linkage is declared but not defined within
this project.
C\C++
Yes
1753
The function '%1s' with external linkage is declared but not defined within
this project.
C\C++
Yes
1755
The tag '%1s' is declared but not used within this project.
C\C++
Yes
CMA Maintenance Warnings
1504
The object '%1s' is only referenced in the translation unit where it is
defined.
C\C++
No
1505
The function '%1s' is only referenced in the translation unit where it is
defined.
C\C++
No
1506
The identifier '%1s' is declared as a typedef and is used elsewhere for a
different kind of declaration.
C\C++
Yes
1507
'%1s' is used as a typedef for different types.
C\C++
Yes
1508
The typedef '%1s' is declared in more than one location.
C\C++
Yes
1511
Inline variable '%1s' has declarations in multiple translation units.
C\C++
Yes
1512
Identifier '%1s' with external linkage has separate declarations in multiple
translation units.
C\C++
Yes
Page 17


---
*Page 17*

Message
ID
Message Text
Language
Multi-
Homed
1513
Identifier '%1s' with external linkage has separate non-defining
declarations in more than one location.
C\C++
Yes
1514
The object '%1s' is only referenced by function '%2s', in the translation unit
where it is defined
C\C++
No
1515
Different files are being used which have the same filename '%1s'.
C\C++
Yes
1516
Different files are being used which have similar filenames '%1s', but with
different case.
C\C++
Yes
1517
Different files are being used which have the same filename '%1s', and
one includes the other.
C\C++
Yes
1520
Functions are indirectly recursive.
C\C++
Yes
1521
Function '%1s' is recursive.
C\C++
No
1525
Object/function '%1s' with external linkage has same identifier as another
object/function with internal linkage.
C\C++
Yes
1526
Object '%1s' with no linkage has same identifier as another object/function
with external linkage.
C\C++
Yes
1527
Object/function '%1s' with internal linkage has same identifier as another
object/function with internal linkage.
C\C++
Yes
1528
Object '%1s' with no linkage has same identifier as another object/function
with internal linkage.
C\C++
Yes
1529
Object '%1s' with no linkage has same identifier as another object with
static storage duration but no linkage.
C\C++
Yes
1531
The object '%1s' is referenced in only one translation unit - but not the one
in which it is defined.
C\C++
No
1532
The function '%1s' is only referenced in one translation unit - but not the
one in which it is defined.
C\C++
No
1533
The object '%1s' is only referenced by function '%2s'.
C\C++
No
1550
Initializer for statically initialized object '%1s' is defined within a different
translation unit.
C++
No
1551
Initializer for statically initialized object '%1s' is defined later within this
translation unit.
C++
No
Page 18


---
*Page 18*

Message
ID
Message Text
Language
Multi-
Homed
1552
Initializer for '%1s' is initialized dynamically within a different translation
unit
C++
No
1553
Initializer for '%1s' is initialized dynamically later within this translation unit
C++
No
1554
Initializer for '%1s' unknown within this project.
C++
No
1555
Function '%1s' refers to '%2s' which is defined later in this translation unit
and is statically initialized.
C++
No
1556
Function '%1s' refers to '%2s' which is defined later in this translation unit
and is dynamically initialized.
C++
No
1557
Function '%1s' refers to '%2s' which is defined within a different translation
unit and is statically initialized.
C++
No
1558
Function '%1s' refers to '%2s' which is defined within a different translation
unit and is dynamically initialized.
C++
No
1559
Function '%1s' refers to '%2s' for which the definition is unknown.
C++
No
1700
Explicitly declared accessible default constructor for '%1s' is not used
within this project.
C++
No
1701
Implicitly declared copy constructor '%1s' is not used within this project.
C++
No
1702
Implicitly declared assignment operator '%1s' is not used within this
project.
C++
No
1703
'%2s' doesn't need to derive from '%1s' virtually.
C++
No
1704
Recursion during initialization of static variable '%1s'.
C\C++
No
1705
Function '%1s' called without initializing call to '%2s'.
C\C++
No
1706
Definition of inline function '%1s' is not the same in all translation units.
C\C++
Yes
1707
Function '%1s' is not using the same aliases.
C\C++
Yes
1708
Function '%1s' is not using the same qualifiers.
C\C++
Yes
1709
Function '%1s' is not using the same parameter names.
C\C++
Yes
1710
Identifiers have the same matching pattern '%1s'.
C\C++
Yes
1711
Identifiers have the same first '%1s' characters '%2s'.
C\C++
Yes
1712
External identifiers have the same first '%1s' characters '%2s'.
C\C++
Yes
Page 19


---
*Page 19*

Message
ID
Message Text
Language
Multi-
Homed
1720
Object/function '%1s' declared in an unnamed namespace has same
identifier as another object/function with internal linkage.
C++
Yes
1721
Object '%1s' with no linkage has same identifier as another object/function
declared in an unnamed namespace.
C++
Yes
1722
Reused non-member object or function '%1s' with static storage duration.
C++
Yes
1723
Reused non-member object or function '%1s' with static storage duration
in the same namespace.
C++
Yes
1724
Static function or private method '%1s' of a class shall be used.
C++
No
1730
This specialization is not declared with its primary template.
C++
No
1750
'%1s' has multiple definitions.
C\C++
Yes
1751
The global object '%1s' is not modified in this project.
C\C++
No
1756
External identifier '%1s' shall be unique.
C\C++
Yes
1757
Shared global data shall be provided through static local objects instead of
'%1s'.
C\C++
No
1758
Object '%1s' with external linkage is not unique.
C\C++
Yes
1759
Object '%1s' with internal linkage is not unique.
C\C++
Yes
1760
This class may be better as a struct - encapsulation value '%1s' exceeds
specified limit of '%2s'
C++
No
CMA Semantic Warnings
1509
'%1s' has external linkage and has multiple definitions.
C\C++
Yes
1510
'%1s' has external linkage and has incompatible declarations.
C\C++
Yes
Serious Resource Leaks
1530
Object '%1s' used with inconsistent allocation methods in different
translation units.
C++
Yes
Context Messages
3966
Used with plain new/delete here.
C++
No
3967
Used with array new/delete here.
C++
No
3968
Used with old malloc/free here.
C++
No
Page 20


---
*Page 20*
