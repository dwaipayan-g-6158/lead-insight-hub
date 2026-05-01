import { createClient } from "@supabase/supabase-js";

const SUPABASE_URL = process.env.SUPABASE_URL;
const SUPABASE_SERVICE_ROLE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY;

if (!SUPABASE_URL || !SUPABASE_SERVICE_ROLE_KEY) {
  console.error("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in environment");
  process.exit(1);
}

const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, {
  auth: { persistSession: false, autoRefreshToken: false },
});

async function resetAllUsers() {
  console.log("Fetching all users...");
  
  const { data, error } = await supabase.auth.admin.listUsers({ perPage: 1000 });
  
  if (error) {
    console.error("Error fetching users:", error.message);
    process.exit(1);
  }

  const users = data.users;
  console.log(`Found ${users.length} user(s)`);

  if (users.length === 0) {
    console.log("No users to delete.");
    return;
  }

  // Delete user_roles first (if table exists)
  console.log("Clearing user_roles table...");
  const { error: rolesError } = await supabase.from("user_roles").delete().neq("user_id", "00000000-0000-0000-0000-000000000000");
  if (rolesError && !rolesError.message.includes("does not exist")) {
    console.warn("Warning clearing user_roles:", rolesError.message);
  }

  // Delete each user
  for (const user of users) {
    console.log(`Deleting user: ${user.email ?? user.id}`);
    const { error: deleteError } = await supabase.auth.admin.deleteUser(user.id);
    if (deleteError) {
      console.error(`  Failed to delete ${user.id}:`, deleteError.message);
    } else {
      console.log(`  ✓ Deleted`);
    }
  }

  console.log("\n✅ All users have been reset!");
}

resetAllUsers();
