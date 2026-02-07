import NavLink from "./NavLink";
import { NAV_ITEMS } from "@/lib/constants";

export default function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-screen">
      {/* Sidebar */}
      <aside className="w-64 bg-[var(--color-sidebar)] flex flex-col shrink-0">
        <div className="p-5 border-b border-white/10">
          <h1 className="text-xl font-bold text-white tracking-tight">Sam</h1>
          <p className="text-xs text-gray-400 mt-0.5">Voice Agent Dashboard</p>
        </div>
        <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.href}
              href={item.href}
              label={item.label}
              icon={item.icon}
            />
          ))}
        </nav>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto">{children}</main>
    </div>
  );
}
