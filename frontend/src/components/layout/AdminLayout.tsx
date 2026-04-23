import { NavLink, Outlet } from 'react-router-dom';
import { LayoutDashboard, Server, Route, Settings, Activity, Calendar } from 'lucide-react';
import { cn } from '../../lib/utils';
import { useAdminStore } from '../../store/adminStore';

const navigation = [
  { name: 'Dashboard', href: '/admin', icon: LayoutDashboard },
  { name: 'Nodes', href: '/admin/nodes', icon: Server },
  { name: 'Paths', href: '/admin/paths', icon: Route },
  { name: 'Schedules', href: '/admin/schedules', icon: Calendar },
  { name: 'Alerts & History', href: '/admin/alerts', icon: Activity },
  { name: 'Settings', href: '/admin/settings', icon: Settings },
];

export function AdminLayout() {
  const topologyId = useAdminStore(s => s.topologyId);
  const panelBuild = (window as any).panel_build_label;

  return (
    <div className="flex h-screen bg-slate-50 dark:bg-slate-900 text-slate-900 dark:text-slate-100 font-sans">
      <div className="w-64 bg-white dark:bg-slate-950 border-r border-slate-200 dark:border-slate-800 flex flex-col shadow-sm relative z-10">
        <div className="flex h-16 shrink-0 items-center px-6 border-b border-slate-200 dark:border-slate-800">
          <span className="font-bold text-lg tracking-tight">FRP Admin</span>
          {panelBuild && <span className="ml-2 px-2 py-0.5 rounded text-[10px] bg-slate-100 text-slate-600 font-mono">{panelBuild}</span>}
        </div>
        <div className="flex flex-1 flex-col overflow-y-auto px-4 py-6 gap-y-1">
          {navigation.map((item) => (
            <NavLink
              key={item.name}
              to={item.href}
              className={({ isActive }) =>
                cn(
                  isActive
                    ? 'bg-blue-50 text-blue-700 dark:bg-blue-900/20 dark:text-blue-400 font-medium'
                    : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-800/50 dark:hover:text-slate-200',
                  'group flex items-center px-3 py-2.5 text-sm font-medium rounded-lg transition-colors'
                )
              }
              end={item.href === '/admin'}
            >
              <item.icon
                className="mr-3 h-5 w-5 shrink-0 transition-colors"
                aria-hidden="true"
              />
              {item.name}
            </NavLink>
          ))}
        </div>
        {topologyId && (
          <div className="p-4 border-t border-slate-200 dark:border-slate-800 text-xs text-slate-500 font-mono break-all text-center">
            Env: {topologyId}
          </div>
        )}
      </div>

      <div className="flex flex-1 flex-col min-w-0 overflow-hidden relative">
        <main className="flex-1 overflow-y-auto p-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
