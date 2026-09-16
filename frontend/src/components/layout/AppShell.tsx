"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import Sidebar from "./Sidebar";
import Topbar from "./Topbar";
import { useProduct } from "./ProductSwitcher";

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const product = useProduct();
  const isLanding = pathname === "/";
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    if (isLanding) {
      delete document.body.dataset.product;
    } else {
      document.body.dataset.product = product;
    }
  }, [product, isLanding]);

  // Close the mobile drawer on navigation
  useEffect(() => {
    setMenuOpen(false);
  }, [pathname]);

  if (isLanding) {
    return (
      <main className="min-h-screen bg-page-bg text-text-primary flex flex-col">
        {children}
      </main>
    );
  }

  return (
    <div className="flex h-screen bg-page-bg text-text-primary overflow-hidden">
      <Sidebar mobileOpen={menuOpen} onCloseMenu={() => setMenuOpen(false)} />
      <div className="flex flex-col flex-1 min-w-0 overflow-hidden bg-page-bg lg:border-l lg:border-border-soft">
        <Topbar onOpenMenu={() => setMenuOpen(true)} />
        <main className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8">
          <div className="max-w-container mx-auto">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}