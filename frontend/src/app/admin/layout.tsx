"use strict";

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return <div className="flex h-full flex-col bg-[#0a0a0c]">{children}</div>;
}
