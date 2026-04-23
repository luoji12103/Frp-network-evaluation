import { useState } from 'react';
import { useAdminStore } from '../../store/adminStore';
import { Server, Activity, AlertTriangle, RefreshCw } from 'lucide-react';

export function Nodes() {
  const { nodes } = useAdminStore();
  const [loading, setLoading] = useState(false);
  const nodesList = Object.entries(nodes || {}).map(([id, data]) => ({ id, ...(data as any) }));

  const handleRefresh = async () => {
    setLoading(true);
    // TODO: implement API fetch call here later
    setTimeout(() => setLoading(false), 500); 
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center pb-4 border-b border-slate-200 dark:border-slate-800">
        <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">Nodes Manager</h1>
        <button
          onClick={handleRefresh}
          disabled={loading}
          className="inline-flex items-center px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg disabled:opacity-50 transition-colors"
        >
          <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
          Refresh Nodes
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {nodesList.map((node) => (
          <div key={node.id} className="bg-white dark:bg-slate-950 p-5 rounded-xl shadow-sm border border-slate-200 dark:border-slate-800 hover:shadow-md transition-shadow">
            <div className="flex justify-between items-start mb-4">
              <div className="flex items-center space-x-3">
                <div className={`p-2 rounded-lg ${node.status === 'online' ? 'bg-green-100 text-green-600' : 'bg-red-100 text-red-600'} shrink-0`}>
                  <Server className="w-5 h-5" />
                </div>
                <div className="min-w-0">
                  <h3 className="text-base font-semibold text-slate-900 dark:text-white truncate" title={node.label || node.id}>
                    {node.label || node.id}
                  </h3>
                  <p className="text-xs text-slate-500 font-mono truncate">{node.ip}</p>
                </div>
              </div>
            </div>
            
            <div className="space-y-2 mt-4 pt-4 border-t border-slate-100 dark:border-slate-800 text-sm">
              <div className="flex justify-between">
                <span className="text-slate-500">Platform</span>
                <span className="text-slate-900 dark:text-slate-200">{node.os || node.platform || 'Unknown'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Role</span>
                <span className="bg-slate-100 dark:bg-slate-800 px-2 py-0.5 rounded text-xs font-medium text-slate-700 dark:text-slate-300">
                  {node.is_server ? 'Server' : 'Client'}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-slate-500">CPU Usage</span>
                <div className="flex items-center">
                   {node.cpu_percent ? (
                     <>
                       <span className="font-semibold text-slate-900 dark:text-slate-200">{node.cpu_percent}%</span>
                       <Activity className="w-3 h-3 ml-1 text-slate-400" />
                     </>
                   ) : (
                     <span className="text-slate-400">N/A</span>
                   )}
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
      
      {nodesList.length === 0 && (
         <div className="flex flex-col items-center justify-center p-12 bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-800 border-dashed rounded-xl">
           <AlertTriangle className="w-12 h-12 text-slate-300 mb-4" />
           <p className="text-lg font-medium text-slate-900 dark:text-white">No nodes connected</p>
           <p className="text-sm text-slate-500 max-w-md text-center mt-2">Deploy agents to your servers to securely monitor network performance.</p>
         </div>
      )}
    </div>
  );
}
