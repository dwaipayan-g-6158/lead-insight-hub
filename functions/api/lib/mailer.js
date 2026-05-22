const { selectAll } = require("./db");

// Notify every admin (user_roles.role = 'admin') that a new self-signup
// happened. Resolves admin emails via userManagement.getAllUsers() — same
// path used by GET /admin/users — because user_roles doesn't carry email.
//
// Fire-and-forget: callers wrap in .catch() and never block the response.
async function notifyAdminsOfSignup(catalystApp, newUser) {
  const fromEmail = process.env.SIGNUP_FROM_EMAIL;
  if (!fromEmail) {
    console.warn("notifyAdminsOfSignup: SIGNUP_FROM_EMAIL not set, skipping.");
    return;
  }

  const zcql = catalystApp.zcql();
  const userMgmt = catalystApp.userManagement();

  const adminRows = await selectAll(
    zcql,
    `SELECT user_id FROM user_roles WHERE role = 'admin'`,
    "user_roles",
  );
  const adminIds = new Set(adminRows.map((r) => String(r.user_id)));
  if (adminIds.size === 0) return;

  let allUsers;
  if (typeof userMgmt.getAllUsers === "function") {
    allUsers = await userMgmt.getAllUsers();
  } else if (typeof userMgmt.listUsers === "function") {
    allUsers = await userMgmt.listUsers();
  } else {
    console.warn("notifyAdminsOfSignup: no list API on userManagement");
    return;
  }
  const list = Array.isArray(allUsers) ? allUsers : allUsers?.users || [];

  const adminEmails = [];
  for (const u of list) {
    const uid = String(u.user_id ?? u.zuid ?? u.id);
    if (!adminIds.has(uid)) continue;
    const e = u.email_id ?? u.email;
    if (e) adminEmails.push(e);
  }
  if (adminEmails.length === 0) return;

  const fullName = [newUser.first_name, newUser.last_name].filter(Boolean).join(" ") || newUser.email_id;
  const subject = `New user joined lead-insight-hub: ${fullName}`;
  const signupTime = new Date().toUTCString();
  const content = [
    `A new teammate just self-signed up for lead-insight-hub.`,
    ``,
    `  Name:   ${fullName}`,
    `  Email:  ${newUser.email_id}`,
    `  Time:   ${signupTime}`,
    ``,
    `They land as role = "user" by default. Open /admin to change their role or remove them if needed.`,
    ``,
    `(You are receiving this because you are an admin on lead-insight-hub.)`,
  ].join("\n");

  // sendMail accepts to_email as string OR string[]; a single batched call
  // keeps the credit cost flat regardless of admin headcount.
  await catalystApp
    .email()
    .sendMail({
      from_email: fromEmail,
      to_email: adminEmails,
      subject,
      content,
    })
    .catch((e) => console.warn("sendMail failed (non-fatal):", e?.message));
}

module.exports = { notifyAdminsOfSignup };
