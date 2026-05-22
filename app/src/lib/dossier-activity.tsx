import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

// Shared state for the single "activity popup" (DossierActivityPopup).
// Mounted at AppShell so both the header pill (clicking an in-flight row)
// and the LeadsListPage's CreateDossierModal (handing off after Generate)
// can drive the same popup without prop-drilling through TanStack Router's
// <Outlet />.

type Ctx = {
  activeRequestId: string | null;
  openActivity: (id: string) => void;
  closeActivity: () => void;
};

const DossierActivityContext = createContext<Ctx | null>(null);

export function DossierActivityProvider({ children }: { children: ReactNode }) {
  const [activeRequestId, setActiveRequestId] = useState<string | null>(null);

  const openActivity = useCallback((id: string) => {
    setActiveRequestId(id);
  }, []);

  const closeActivity = useCallback(() => {
    setActiveRequestId(null);
  }, []);

  const value = useMemo<Ctx>(
    () => ({ activeRequestId, openActivity, closeActivity }),
    [activeRequestId, openActivity, closeActivity],
  );

  return (
    <DossierActivityContext.Provider value={value}>
      {children}
    </DossierActivityContext.Provider>
  );
}

export function useDossierActivity(): Ctx {
  const ctx = useContext(DossierActivityContext);
  if (!ctx) {
    throw new Error(
      "useDossierActivity must be used inside <DossierActivityProvider>",
    );
  }
  return ctx;
}
