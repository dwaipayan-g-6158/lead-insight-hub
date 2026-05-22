const express = require("express");

const router = express.Router();

router.get("/", (req, res) => {
  res.json({
    userId: req.userId,
    email: req.user?.email_id ?? null,
    firstName: req.user?.first_name ?? null,
    lastName: req.user?.last_name ?? null,
    role: req.role,
    isAdmin: req.isAdmin,
    roles: [req.role],
  });
});

router.get("/role", (req, res) => {
  res.json({
    userId: req.userId,
    role: req.role,
    isAdmin: req.isAdmin,
    roles: [req.role],
  });
});

module.exports = router;
