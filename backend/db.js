const { Pool } = require("pg");

const pool = new Pool({
  user: "tree_user",
  host: "localhost",
  database: "tree_db",
  password: "password123",
  port: 5432,
});

module.exports = pool;
