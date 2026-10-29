Traceability explorer
=====================

Search or sort the tables to find a behavior and follow its parent links.
The tables include superseded records so that changed decisions remain visible;
current-only counts and lifecycle explanations are in :doc:`index`.

Each row is one authored record. Coverage tags describe implementation, while
``status`` or ``status_crs`` describes its review state. A linked source/test file
is candidate evidence, not a verification verdict.

Stakeholder needs and feature groups
------------------------------------

.. needtable:: Stakeholder requirements
   :filter: type == "req-stkh" and not is_part
   :columns: id;title;status_crs as "Review state";tags as "Implementation";clustered_by as "Feature"
   :colwidths: 23;31;13;13;20
   :style: DATATABLES
   :sort: id

System contracts and their parents
----------------------------------

.. needtable:: System requirements
   :filter: type == "req-sys" and not is_part
   :columns: id;title;status as "Review state";tags as "Implementation";req_satisfies as "Satisfies"
   :colwidths: 23;31;13;13;20
   :style: DATATABLES
   :sort: id

Software behavior and its parents
----------------------------------

.. needtable:: Software requirements
   :filter: type == "req-sw" and not is_part
   :columns: id;title;status as "Review state";tags as "Implementation";req_satisfies as "Satisfies"
   :colwidths: 23;31;13;13;20
   :style: DATATABLES
   :sort: id

For decisions that have changed or work that is not yet available, see
:doc:`decisions-and-gaps`.
