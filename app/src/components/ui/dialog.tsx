"use client";

import * as React from "react";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { X } from "lucide-react";

import { cn } from "@/lib/utils";

const Dialog = DialogPrimitive.Root;

const DialogTrigger = DialogPrimitive.Trigger;

const DialogPortal = DialogPrimitive.Portal;

const DialogClose = DialogPrimitive.Close;

const DialogOverlay = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Overlay>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Overlay>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Overlay
    ref={ref}
    className={cn(
      "fixed inset-0 z-50 bg-black/80  data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0",
      className,
    )}
    {...props}
  />
));
DialogOverlay.displayName = DialogPrimitive.Overlay.displayName;

type DialogContentProps = React.ComponentPropsWithoutRef<
  typeof DialogPrimitive.Content
> & {
  // When true, the built-in top-right X close button is omitted. Used by
  // DossierActivityPopup to lock the popup open while a dossier is in
  // flight — only the "Run in background" action should close it.
  hideClose?: boolean;
  // CSS selector for an element this dialog should MINIMIZE INTO (and emerge
  // FROM) — e.g. the top-right "Dossier Requests" pill or the account menu.
  // When set, the default centre-zoom animation is swapped for a FLIP-style
  // "fly to corner" so closing the dossier popup / reset dialog reads as
  // minimizing toward its top-right trigger rather than drifting top-left.
  // If the target is missing or hidden (e.g. the pill below the md breakpoint),
  // it falls back to the top-right viewport corner.
  flyTarget?: string;
};

const DIALOG_ANIM_DEFAULT =
  "data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 data-[state=closed]:slide-out-to-left-1/2 data-[state=closed]:slide-out-to-top-[48%] data-[state=open]:slide-in-from-left-1/2 data-[state=open]:slide-in-from-top-[48%]";

const DialogContent = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Content>,
  DialogContentProps
>(({ className, children, hideClose, flyTarget, ...props }, ref) => {
  // FLIP "fly to pill" support. The dialog's resting centre is deterministic
  // (centred via left/top-50% + translate(-50%,-50%)), so we derive it from the
  // viewport instead of reading the mid-animation rect; offsetWidth is
  // transform-independent, giving the true resting width for the scale ratio.
  //
  // We compute inside the REF CALLBACK rather than a layout effect: Radix's
  // Presence defers mounting the Content node, so on the component's first
  // commit the node isn't attached yet — a layout effect would read a null ref
  // and (with stable deps) never re-run. The ref callback instead fires exactly
  // when Radix attaches the node, and again with null on unmount (which Radix
  // does only AFTER the close animation finishes), giving us a clean teardown.
  //
  // The --fly-* offsets are written to <html>, not the node: Radix owns
  // Content's inline `style` (pointer-events) and strips custom properties
  // poked onto the node, but CSS custom properties INHERIT, so the keyframes'
  // var(--fly-*) on .dialog-fly resolve from documentElement. Only one
  // fly-dialog can be open at a time (both are modal), and the teardown clears
  // the vars so they never leak to a later dialog.
  const flyTeardown = React.useRef<(() => void) | null>(null);
  const setRefs = React.useCallback(
    (node: HTMLDivElement | null) => {
      if (typeof ref === "function") ref(node);
      else if (ref)
        (ref as React.MutableRefObject<HTMLDivElement | null>).current = node;

      if (flyTarget === undefined) return;
      if (!node) {
        flyTeardown.current?.();
        flyTeardown.current = null;
        return;
      }
      const root = document.documentElement;
      const compute = () => {
        const restW = node.offsetWidth || 1;
        const restCx = window.innerWidth / 2;
        const restCy = window.innerHeight / 2;
        // Fallback: top-right viewport corner — where both the pill and the
        // account menu live — for when the selector is absent or display:none.
        let tCx = window.innerWidth - 32;
        let tCy = 28;
        let tW = 48;
        const target = flyTarget ? document.querySelector(flyTarget) : null;
        if (target) {
          const r = target.getBoundingClientRect();
          if (r.width > 0 && r.height > 0) {
            tCx = r.left + r.width / 2;
            tCy = r.top + r.height / 2;
            tW = r.width;
          }
        }
        root.style.setProperty("--fly-x", `${Math.round(tCx - restCx)}px`);
        root.style.setProperty("--fly-y", `${Math.round(tCy - restCy)}px`);
        root.style.setProperty("--fly-s", Math.max(tW / restW, 0.04).toFixed(3));
      };
      compute();
      window.addEventListener("resize", compute);
      flyTeardown.current = () => {
        window.removeEventListener("resize", compute);
        root.style.removeProperty("--fly-x");
        root.style.removeProperty("--fly-y");
        root.style.removeProperty("--fly-s");
      };
    },
    [ref, flyTarget],
  );

  return (
    <DialogPortal>
      <DialogOverlay />
      <DialogPrimitive.Content
        ref={setRefs}
        className={cn(
          "fixed left-[50%] top-[50%] z-50 grid w-full max-w-lg translate-x-[-50%] translate-y-[-50%] gap-4 border bg-background p-6 shadow-lg duration-200 sm:rounded-lg",
          flyTarget !== undefined ? "dialog-fly" : DIALOG_ANIM_DEFAULT,
          className,
        )}
        {...props}
      >
        {children}
        {!hideClose && (
          <DialogPrimitive.Close className="absolute right-4 top-4 rounded-sm opacity-70 ring-offset-background transition-opacity hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:pointer-events-none data-[state=open]:bg-accent data-[state=open]:text-muted-foreground">
            <X className="h-4 w-4" />
            <span className="sr-only">Close</span>
          </DialogPrimitive.Close>
        )}
      </DialogPrimitive.Content>
    </DialogPortal>
  );
});
DialogContent.displayName = DialogPrimitive.Content.displayName;

const DialogHeader = ({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={cn("flex flex-col space-y-1.5 text-center sm:text-left", className)} {...props} />
);
DialogHeader.displayName = "DialogHeader";

const DialogFooter = ({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
  <div
    className={cn("flex flex-col-reverse sm:flex-row sm:justify-end sm:space-x-2", className)}
    {...props}
  />
);
DialogFooter.displayName = "DialogFooter";

const DialogTitle = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Title>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Title>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Title
    ref={ref}
    className={cn("text-lg font-semibold leading-none tracking-tight", className)}
    {...props}
  />
));
DialogTitle.displayName = DialogPrimitive.Title.displayName;

const DialogDescription = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Description>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Description>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Description
    ref={ref}
    className={cn("text-sm text-muted-foreground", className)}
    {...props}
  />
));
DialogDescription.displayName = DialogPrimitive.Description.displayName;

export {
  Dialog,
  DialogPortal,
  DialogOverlay,
  DialogTrigger,
  DialogClose,
  DialogContent,
  DialogHeader,
  DialogFooter,
  DialogTitle,
  DialogDescription,
};
