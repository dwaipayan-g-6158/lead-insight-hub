// Per-user completion-feedback preferences + effects (sound + desktop
// notification + activity-pill pulse). Preferences live in localStorage and
// default OFF — sound and OS notifications are intrusive, so they are strictly
// opt-in. All effects are best-effort and never throw into the caller.

import { isDesktopEnv } from "./platform";

const SOUND_KEY = "_lih_sound";
const NOTIFY_KEY = "_lih_notify";

/* ---------------- preference state ---------------- */

export function getSoundEnabled(): boolean {
  try {
    return localStorage.getItem(SOUND_KEY) === "1";
  } catch {
    return false;
  }
}

export function setSoundEnabled(on: boolean): void {
  try {
    localStorage.setItem(SOUND_KEY, on ? "1" : "0");
  } catch {
    /* localStorage unavailable — no-op */
  }
}

export function getNotifyEnabled(): boolean {
  try {
    return localStorage.getItem(NOTIFY_KEY) === "1";
  } catch {
    return false;
  }
}

export function setNotifyEnabled(on: boolean): void {
  try {
    localStorage.setItem(NOTIFY_KEY, on ? "1" : "0");
  } catch {
    /* no-op */
  }
}

/**
 * Toggle desktop notifications. Turning ON triggers the browser permission
 * prompt (must be called from a user gesture). Returns the resulting enabled
 * state so the caller can reflect it in the UI / toast the outcome.
 */
export async function toggleDesktopNotifications(next: boolean): Promise<boolean> {
  if (!next) {
    setNotifyEnabled(false);
    return false;
  }
  if (typeof Notification === "undefined") return false;
  let perm = Notification.permission;
  if (perm === "default") {
    try {
      perm = await Notification.requestPermission();
    } catch {
      return false;
    }
  }
  const ok = perm === "granted";
  setNotifyEnabled(ok);
  return ok;
}

/* ---------------- effects ---------------- */

// Lazily-created AudioContext, reused across chimes. Created on first play
// (always inside a user-initiated flow), so autoplay policies are satisfied.
let audioCtx: AudioContext | null = null;
function getAudioCtx(): AudioContext | null {
  if (typeof window === "undefined") return null;
  const AC =
    window.AudioContext ||
    (window as unknown as { webkitAudioContext?: typeof AudioContext })
      .webkitAudioContext;
  if (!AC) return null;
  try {
    if (!audioCtx) audioCtx = new AC();
    return audioCtx;
  } catch {
    return null;
  }
}

/**
 * A short, pleasant two-note "ta-da" chime synthesized via Web Audio — no
 * external asset, so it never trips the Catalyst client CSP. No-op unless the
 * user opted in.
 */
export function playSuccessChime(): void {
  // Desktop browser only — silent on mobile and inside a PWA.
  if (!isDesktopEnv()) return;
  if (!getSoundEnabled()) return;
  const ctx = getAudioCtx();
  if (!ctx) return;
  try {
    if (ctx.state === "suspended") void ctx.resume();
    const now = ctx.currentTime;
    // E5 then B5 — a clean rising perfect-fifth that reads as "done/success".
    const notes = [
      { f: 659.25, t: 0 },
      { f: 987.77, t: 0.12 },
    ];
    for (const { f, t } of notes) {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "sine";
      osc.frequency.value = f;
      const start = now + t;
      gain.gain.setValueAtTime(0.0001, start);
      gain.gain.exponentialRampToValueAtTime(0.16, start + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, start + 0.45);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start(start);
      osc.stop(start + 0.5);
    }
  } catch {
    /* audio failed — silent */
  }
}

/**
 * Fire an OS/desktop notification when the dossier finishes — but only if the
 * user opted in, granted permission, AND the tab is backgrounded (no point
 * notifying when they're already looking at the app). Clicking focuses the tab.
 */
export function notifyDossierReady(name: string, leadId?: string): void {
  if (!getNotifyEnabled()) return;
  if (typeof Notification === "undefined" || Notification.permission !== "granted")
    return;
  if (typeof document !== "undefined" && !document.hidden) return;
  try {
    const n = new Notification("Dossier ready", {
      body: name ? `${name} is ready to view.` : "Your dossier is ready to view.",
      tag: leadId ? `dossier-${leadId}` : undefined,
    });
    n.onclick = () => {
      try {
        window.focus();
      } catch {
        /* no-op */
      }
      n.close();
    };
  } catch {
    /* notification failed — silent */
  }
}

/**
 * One-shot celebratory glow/scale pulse on the Dossier Requests pill so the
 * completion is noticeable even if the toast was missed. Restarts cleanly if
 * called again. CSS suppresses it under prefers-reduced-motion.
 */
export function pulseActivityPill(): void {
  if (typeof document === "undefined") return;
  const el = document.getElementById("dossier-activity-pill");
  if (!el) return;
  el.classList.remove("pill-celebrate");
  // Force reflow so re-adding the class restarts the animation.
  void el.offsetWidth;
  el.classList.add("pill-celebrate");
  window.setTimeout(() => el.classList.remove("pill-celebrate"), 1600);
}
