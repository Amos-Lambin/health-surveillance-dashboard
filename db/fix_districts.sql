-- Align districts with the DHIS2 Sierra Leone demo (13 districts; "Western Area" is one).
-- Removes the synthetic rows first (they point at the old district ids), then reloads.
-- Run in the Supabase SQL editor, then re-run synthetic_weekly.py.
delete from alert_log;
delete from weekly_cases;
delete from districts;

insert into districts (name, dhis2_uid) values
  ('Bo',                'O6uvpzGd5pu'),
  ('Bombali',           'fdc6uOvgoji'),
  ('Bonthe',            'lc3eMKXaEfw'),
  ('Kailahun',          'jUb8gELQApl'),
  ('Kambia',            'PMa2VCrupOd'),
  ('Kenema',            'kJq2mPyFEHo'),
  ('Koinadugu',         'qhqAxPSTUXp'),
  ('Kono',              'Vth0fbpFcsO'),
  ('Moyamba',           'jmIPBj66vD6'),
  ('Port Loko',         'TEQlaapDQoK'),
  ('Pujehun',           'bL4ooGhyHRQ'),
  ('Tonkolili',         'eIQbndfxQMb'),
  ('Western Area',      'at6UHUQatSo');
