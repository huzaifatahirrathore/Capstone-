const express = require("express");
const multer = require("multer");
const axios = require("axios");
const FormData = require("form-data");
const fs = require("fs");
const cors = require("cors");

const app = express();
app.use(cors());

const upload = multer({ dest: "uploads/" });

app.post("/compare", upload.fields([
  { name: "before" },
  { name: "after" }
]), async (req, res) => {
  try {
    const form = new FormData();

    form.append("before", fs.createReadStream(req.files["before"][0].path));
    form.append("after", fs.createReadStream(req.files["after"][0].path));

    const response = await axios.post(
      "http://localhost:5000/compare",
      form,
      {
        headers: form.getHeaders(),
        responseType: "stream"
      }
    );

    res.setHeader("Content-Type", "image/jpeg");

    response.data.pipe(res);

    response.data.on("end", () => {
      fs.unlink(req.files["before"][0].path, () => {});
      fs.unlink(req.files["after"][0].path, () => {});
    });

    response.data.on("error", (err) => {
      console.error("Stream error:", err);
      res.status(500).json({ error: "Stream failed" });
    });

  } catch (err) {
    console.error("Compare Error:", err.message);
    res.status(500).json({ error: "Compare failed" });
  }
});