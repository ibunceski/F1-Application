import { Outlet } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';

export function AppShell() {
  return (
    <div className="min-h-screen bg-f1-dark">
      <Sidebar />
      <div className="min-h-screen lg:ml-60">
        <TopBar />
        <main className="h-[calc(100vh-4rem)] overflow-y-auto px-4 py-5 pb-24 sm:px-6 lg:pb-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
