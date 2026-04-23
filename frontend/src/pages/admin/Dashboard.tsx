import { useAdminStore } from '../../store/adminStore';
import { Server, AlertCircle, PlayCircle } from 'lucide-react';

export function Dashboard() {
  const { nodes, alerts, latestRuns } = useAdminStore();
  
  const nodesList = Object.values(nodes || {});
  const onlineNodes = nodesList.filter((n: any) => n.status === 'online').length;
  
  const stats = [
    { name: 'Total Nodes', value: nodesList.length, icon: Server, color: 'text-blue-600', bg: 'bg-blue-100' },
    { name: 'Online Nodes', value: onlineNodes, icon: Server, color: 'text-green-600', bg: 'bg-green-100' },
    { name: 'Active Alerts', value: alerts?.length || 0, icon: AlertCircle, color: 'text-red-600', bg: 'bg-red-100' },
    { name: 'Recent Runs', value: latestRuns?.length || 0, icon: PlayCircle, color: 'text-purple-600', bg: 'bg-purple-100' }
  ];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">Overview</h1>
      
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((stat) => (
          <div key={stat.name} className="bg-white dark:bg-slate-950 p-6 rounded-xl shadow-sm border border-slate-200 dark:border-slate-800">
            <div className="flex items-center">
              <div className={`p-3 rounded-lg ${stat.bg} ${stat.color} dark:bg-opacity-20`}>
                <stat.icon className="w-6 h-6" />
              </div>
              <div className="ml-4">
                <p className="text-sm font-medium text-slate-500 dark:text-slate-400">{stat.name}</p>
                <p className="text-2xl font-semibold text-slate-900 dark:text-white">{stat.value}</p>
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-8">
        <div className="bg-white dark:bg-slate-950 rounded-xl shadow-sm border border-slate-200 dark:border-slate-800 p-6">
             <h2 className="text-lg font-semibold mb-4 text-slate-900 dark:text-white">Recent Alerts</h2>
             {alerts?.length > 0 ? (
               <div className="space-y-3">
                  {alerts.slice(0, 5).map((alert: any, i) => (
                    <div key={i} className="p-3 bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400 rounded-lg flex items-start gap-3">
                       <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
                       <div>
                         <p className="text-sm font-medium">{alert.rule_name || 'Alert'}</p>
                         <p className="text-xs mt-1 opacity-80">{alert.message || 'Threshold exceeded'}</p>
                       </div>
                    </div>
                  ))}
               </div>
             ) : (
               <p className="text-sm text-slate-500 dark:text-slate-400">No active alerts.</p>
             )}
        </div>

        <div className="bg-white dark:bg-slate-950 rounded-xl shadow-sm border border-slate-200 dark:border-slate-800 p-6">
             <h2 className="text-lg font-semibold mb-4 text-slate-900 dark:text-white">Recent Task Runs</h2>
             {latestRuns?.length > 0 ? (
               <div className="space-y-3">
                  {latestRuns.slice(0, 5).map((run: any, i) => (
                    <div key={i} className="p-3 border border-slate-100 dark:border-slate-800 rounded-lg flex justify-between items-center bg-slate-50 dark:bg-slate-900/50">
                       <div>
                         <p className="text-sm font-medium text-slate-900 dark:text-white">{run.action}</p>
                         <p className="text-xs text-slate-500 mt-1">{new Date(run.started_at * 1000).toLocaleString()}</p>
                       </div>
                       <span className={`text-xs px-2 py-1 rounded-full font-medium ${run.status === 'completed' ? 'bg-green-100 text-green-700' : run.status === 'failed' ? 'bg-red-100 text-red-700' : 'bg-blue-100 text-blue-700'}`}>
                         {run.status}
                       </span>
                    </div>
                  ))}
               </div>
             ) : (
               <p className="text-sm text-slate-500 dark:text-slate-400">No recent runs.</p>
             )}
        </div>
      </div>
    </div>
  );
}
