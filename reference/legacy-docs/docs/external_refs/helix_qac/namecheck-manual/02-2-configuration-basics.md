# 2 | Configuration Basics

2 | Configuration Basics
Previously, the Namecheck NCF file was set as a property of the project. A set of buttons in the General tab of the Project
Properties dialog could be used to choose an NCF file. It could also be set using the qacli admin command.
Namecheck is installed as a full component within the toolchain and is managed in the same way as other components.
Options are displayed and set from the Analysis tab of the Helix QAC Project Properties dialog, and the NCF file is
specified through the -namerulefile option. You would typically use one NCF file for C language projects, and
another for C++ language projects, although, if required, the same NCF file can be used for both C and C++ files, if you
wish to enforce the same naming convention in both languages.
Note:
Setting the NCF file through the qacli admin -N option is deprecated but will still work, provided that
Namecheck has been set as an active component for the project.
It will also be necessary to provide any additional messages mentioned in the configuration file, through a user message
file. Message 4800 is reserved in the standard message file as a default configuration entry.
Page 7


---
*Page 7*
