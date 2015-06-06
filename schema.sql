drop table if exists entries;
drop table if exists mentions;

create table entries (
  id integer primary key autoincrement,
  title text not null,
  day text not null,
  month text not null,
  year text not null
);
