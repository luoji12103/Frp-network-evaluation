import { usePublicStore } from '../../store/publicStore';
import { Server, Route, AlertTriangle, Activity } from 'lucide-react';

export function PublicOverview() {
  const { summary, alerts, paths } = usePublicStore();
  const summaryData = summary || {};
  
  const pathList = Array.isArray(paths) ? paths : Object.values(paths || {});

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
         <div className="bg-white dark:bg-slate-950 p-6 rounded-xl border border-slate-200 dark:border-slate-800">
            <h3 className="text-sm font-medium text-slate-500 mb-1 flex items-center"><Server className="w-4 h-4 mr-2" /> Total Nodes</h3>
            <p className="text-3xl font-bold text-slate-900 dark:text-white">{summaryData.nodesCount || 0}</p>
         </div>
         <div className="bg-white dark:bg-slate-950 p-6 rounded-xl border border-slate-200 dark:border-slate-800">
            <h3 className="text-sm font-medium text-slate-500 mb-1 flex items-center"><Activity className="w-4 h-4 mr-2 text-green-500" /> Online Nodes</h3>
            <p className="text-3xl font-bold text-green-600 dark:text-green-500">{summaryData.onlineCount || 0}</p>
         </div>
         <div className="bg-white dark:bg-slate-950 p-6 rounded-xl border border-slate-200 dark:border-slate-800">
            <h3 className="text-sm font-medium text-slate-500 mb-1 flex items-center"><AlertTriangle className="w-4 h-4 mr-2 text-red-500" /> Open Alerts</h3>
            <p className="text-3xl font-bold text-red-600 dark:text-red-500">{alerts?.length || 0}</p>
         </div>
         <div className="bg-white dark:bg-slate-950 p-6 rounded-xl border border-slate-200 dark:border-slate-800">
            <h3 className="text-sm font-medium text-slate-500 mb-1 flex items-center"><Route className="w-4 h-4 mr-2 text-blue-500" /> Paths Monitored</h3>
            <p className="text-3xl font-bold text-blue-600 dark:text-blue-500">{pathList.length}</p>
         </div>
      </div>

      <div className="bg-white dark:bg-slate-950 rounded-xl border border-slate-200 dark:border-slate-800 overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50">
          <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Active Network Paths</h2>
        </div>
        <div className="divide-y divide-slate-100 dark:divide-slate-800">
           {pathList.length > 0 ? pathList.map((p: any, i: number) => (
             <div key={i} className="px-6 py-4 hover:bg-slate-50 dark:hover:bg-slate-900/50 transition-colors flex justify-between items-center">
                <div className="flex items-center gap-3">
                  <Route className="text-slate-400 w-5 h-5" />
                  <span className="font-medium text-slate-900 dark:text-slate-100">{p.id || `${p.source}->${p.dest}`}</span>
                </div>
                <div className="flex items-center gap-4 text-sm font-mono opacity-80">
                  <span>PING: {p.metrics?.rtt_avg ? `${p.metrics.rtt_avg.toFixed(1)}ms` : '-'}</span>
                  <span>LOSS: {p.metrics?.loss_percent !== undefined ? `${p.metrics.loss_percent}%` : '-'}</span>
                </div>
             </div>
           )) : (
             <div className="p-8 text-center text-slate-500">No paths data</div>
           )}
        </div>
      </div>
    </div>
  );
}

export function PublicDetail() {
  const { pageInfo, path_id, role } = usePublicStore();
  return (
    <div className="bg-white dark:bg-slate-950 p-8 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm text-center">
      <Activity className="w-12 h-12 text-blue-500 mx-auto mb-4" />
      <h2 className="text-2xl font-bold text-slate-900 dark:text-white mb-2">
        {pageInfo?.kind === 'path' ? `Path Detail: ${path_id}` : `Role Detail: ${role}`}
      </h2>
      <p className="text-slate-500 dark:text-slate-400 max-w-lg mx-auto">
        Detailed metrics and historical charts for this specific {pageInfo?.kind} will be rendered here.
      </p>
    </div>
  );
}
