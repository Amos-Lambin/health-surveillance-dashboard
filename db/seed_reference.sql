-- Reference data. Districts follow the DHIS2 Sierra Leone demo.
-- Check names against your downloaded demo and fix any mismatch.
insert into districts (name) values
  ('Bo'), ('Bombali'), ('Bonthe'), ('Kailahun'), ('Kambia'), ('Kenema'),
  ('Koinadugu'), ('Kono'), ('Moyamba'), ('Port Loko'), ('Pujehun'),
  ('Tonkolili'), ('Western Area Rural'), ('Western Area Urban')
on conflict do nothing;

insert into diseases (name, icd10) values
  ('Malaria',   'B50-B54'),
  ('Measles',   'B05'),
  ('Cholera',   'A00'),
  ('Typhoid fever', 'A01.0')
on conflict do nothing;
