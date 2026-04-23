import { useState } from 'react';
import { useAdminStore } from '../../store/adminStore';
import { Route, Search, Activity, PlayCircle } from 'lucide-react';

export function Paths() {
  const { nodes } = useAdminStore();
  const [searchTerm, setSearchTerm] = useState('');
  
  // Synthesize paths from nodes (Assuming a mesh network or node-defined paths)
  const paths: any[] = [];
  Object.values(nodes || {}).forEach((node: any) => {
    if (node.paths) {
      Object.entries(node.paths).forEach(([destId, pathData]: [string, any]) => {
        paths.push({
          id: `${node.id}->${destId}`,
          source: node.id,
          dest: destId,
          ...pathData
        });
      });
    }
  });

  const filteredPaths = paths.filter(p => 
    p.id.toLowerCase().includes(searchTerm.toLowerCase()) || 
    p.source.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center pb-4 border-b border-slate-200 dark:border-slate-800 gap-4">
        <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">Network Paths</h1>
        <div className="relative w-full sm:w-72">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 w-4 h-4" />
          <input 
            type="text" 
            placeholder="Search paths..."
            value={searchTerm}
            onChange={e => setSearchTerm(e.target.value)}
            className="w-full pl-9 pr-4 py-2 bg-white dark:bg-slate-950 border border-slate-300 dark:border-slate-700 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
      </div>

      {paths.length > 0 ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
          {filteredPaths.map((path: any) => (
            <div key={path.id} className="bg-white dark:bg-slate-950 rounded-xl shadow-sm border border-slate-200 dark:border-slate-800 p-5 shrink-0 hover:shadow-md transition-shadow">
              <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-3 mb-3">
                 <div className="flex items-center space-x-2 text-sm font-medium text-slate-900 dark:text-slate-100">
                    <span className="truncate max-w-[100px]" title={path.source}>{path.source}</span>
                    <Route className="w-4 h-4 text-slate-400 shrink-0" />
                    <span className="truncate max-w-[100px]" title={path.dest}>{path.dest}</span>
                 </div>
                 <span className={`px-2 py-0.5 text-xs rounded font-medium ${path.status === 'ok' ? 'bg-green-100 bg-opacity-20 text-green-600 dark:text-green-400' : 'bg-red-100 bg-opacity-20 text-red-600 dark:text-red-400'}`}>
                    {path.status || 'unknown'}
                 </span>
              </div>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between items-center text-slate-500 dark:text-slate-400">
                  <span>Latency (avg)</span>
                  <span className="font-mono text-slate-900 dark:text-slate-200">
                    {path.metrics?.rtt_avg ? `${path.metrics.rtt_avg.toFixed(2)}ms` : '-'}
                  </span>
                </div>
                <div className="flex justify-between items-center text-slate-500 dark:text-slate-400">
                  <span>Packet Loss</span>
                  <span className="font-mono text-slate-900 dark:text-slate-200">
                    {path.metrics?.loss_percent !== undefined ? `${path.metrics.loss_percent}%` : '-'}
                  </span>
                </div>
              </div>
              <div className="mt-4 pt-3 border-t border-slate-100 dark:border-slate-800 flex justify-end gap-2">
                 <button className="p-1.5 text-slate-400 hover:text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded transition-colors" title="View Metrics">
                   <Activity className="w-4 h-4" />
                 </button>
                 <button className="p-1.5 text-slate-400 hover:text-purple-600 hover:bg-purple-50 dark:hover:bg-purple-900/20 rounded transition-colors" title="Test Now">
                   <PlayCircle className="w-4 h-4" />
                 </button>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="text-center p-12 bg-white dark:bg-slate-950 rounded-xl border border-dashed border-slate-300 dark:border-slate-800">
           <Route className="w-8 h-8 text-slate-300 mx-auto mb-3" />
           <p className="text-slate-600 dark:text-slate-400 text-sm">No path statistics available currently.</p>
        </div>
      )}
    </div>
  );
}
