const pool = require("./db");

pool.query("SELECT NOW()", (err, res) => {
  if (err) console.error(err);
  else console.log(res.rows);
  process.exit();
});
