drop table if exists entries;
drop table if exists mentions;

create table entries (
  id integer primary key autoincrement,
  title text not null,
  text text not null,
  date_published text not null
);

create table mentions(
  id integer primary key autoincrement,
  content text not null,
  source_url text not null,
  target_url text not null,
  post_date text not null
);