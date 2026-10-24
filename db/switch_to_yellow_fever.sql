-- The DHIS2 IDSR Weekly data set has no typhoid. Replace it with Yellow fever (ICD-10 A95).
-- Keeps the same disease id, so nothing else needs to change.
update diseases set name = 'Yellow fever', icd10 = 'A95' where name = 'Typhoid fever';
delete from web_interest where term = 'Typhoid fever';
