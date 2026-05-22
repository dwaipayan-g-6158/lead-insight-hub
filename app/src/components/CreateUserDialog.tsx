import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { useServerFn } from "@/lib/use-server-fn";
import { adminCreateUser, type AdminUser } from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { UserPlus, Loader2 } from "lucide-react";

const schema = z
  .object({
    first_name: z.string().trim().min(1, "Required"),
    last_name: z.string().trim().optional().default(""),
    email_id: z.string().trim().toLowerCase().email("Invalid email"),
    role: z.enum(["user", "admin"]).default("user"),
  });
type FormValues = z.infer<typeof schema>;

export function CreateUserDialog({
  onCreated,
}: {
  onCreated: (u: AdminUser) => void;
}) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const create = useServerFn(adminCreateUser);
  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      first_name: "",
      last_name: "",
      email_id: "",
      role: "user",
    },
  });

  const onSubmit = async (values: FormValues) => {
    setBusy(true);
    try {
      const u = await create({
        data: { ...values, last_name: values.last_name || "" },
      });
      toast.success(
        `Invited ${values.email_id} — they'll receive an email to set their password.`,
      );
      onCreated(u);
      form.reset();
      setOpen(false);
    } catch (e) {
      toast.error((e as Error)?.message || "Create failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        setOpen(o);
        if (!o) form.reset();
      }}
    >
      <DialogTrigger asChild>
        <Button size="sm">
          <UserPlus className="h-4 w-4 mr-2" /> Create user
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Create user</DialogTitle>
          <DialogDescription>
            Add a teammate to the workspace. They'll receive an email from
            Catalyst with a link to set their password.
          </DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form
            onSubmit={form.handleSubmit(onSubmit)}
            className="space-y-3"
            noValidate
          >
            <div className="grid grid-cols-2 gap-3">
              <FormField
                name="first_name"
                control={form.control}
                render={({ field }) => (
                  <FormItem>
                    <FormLabel htmlFor="cud-first-name">First name</FormLabel>
                    <FormControl>
                      <Input
                        id="cud-first-name"
                        autoComplete="given-name"
                        {...field}
                        autoFocus
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                name="last_name"
                control={form.control}
                render={({ field }) => (
                  <FormItem>
                    <FormLabel htmlFor="cud-last-name">
                      Last name{" "}
                      <span className="text-muted-foreground font-normal">
                        (optional)
                      </span>
                    </FormLabel>
                    <FormControl>
                      <Input
                        id="cud-last-name"
                        autoComplete="family-name"
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>
            <FormField
              name="email_id"
              control={form.control}
              render={({ field }) => (
                <FormItem>
                  <FormLabel htmlFor="cud-email">Email</FormLabel>
                  <FormControl>
                    <Input
                      id="cud-email"
                      type="email"
                      autoComplete="email"
                      inputMode="email"
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              name="role"
              control={form.control}
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Role</FormLabel>
                  <Select onValueChange={field.onChange} value={field.value}>
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      <SelectItem value="user">user</SelectItem>
                      <SelectItem value="admin">admin</SelectItem>
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />
            <DialogFooter className="pt-2">
              <Button
                type="button"
                variant="ghost"
                onClick={() => setOpen(false)}
                disabled={busy}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={busy}>
                {busy && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                Create user
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
