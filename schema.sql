drop table if exists entries;
create table entries (
  id integer primary key autoincrement,
  slug text not null,
  published date not null
);

drop table if exists catagories;
create table catagories (
  id integer primary key autoincrement,
  slug text not null,
  published date not null,
  catagory text not null,
  FOREIGN KEY (slug) REFERENCES entries(slug)
);