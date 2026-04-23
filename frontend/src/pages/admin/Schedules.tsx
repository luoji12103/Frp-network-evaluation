import { useState } from 'react';
import { useAdminStore } from '../../store/adminStore';
import { Calendar, PlayCircle, PlusCircle, StopCircle, RefreshCw } from 'lucide-react';

export function Schedules() {
  const { schedules } = useAdminStore();
  const [searchTerm, setSearchTerm] = useState('');

  const schedList = Array.isArray(schedules) ? schedules : Object.values(schedules || {});
  const filtered = schedList.filter((s:any) => 
     s.name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
     s.action?.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center pb-4 border-b border-slate-200 dark:border-slate-800 gap-4">
        <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">Active Schedules</h1>
        <div className="flex w-full sm:w-auto items-center gap-2">
          <input 
            type="text" 
            placeholder="Search schedules..."
            value={searchTerm}
            onChange={e => setSearchTerm(e.target.value)}
            className="w-full sm:w-64 px-3 py-2 bg-white dark:bg-slate-950 border border-slate-300 dark:border-slate-700 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <button className="flex-shrink-0 p-2 text-white bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors" title="Create Schedule">
            <PlusCircle className="w-5 h-5" />
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {filtered.map((s: any, idx: number) => (
          <div key={idx} className="bg-white dark:bg-slate-950 p-5 rounded-xl shadow-sm border border-slate-200 dark:border-slate-800 flex flex-col justify-between hover:shadow-md transition-shadow">
            <div className="flex justify-between items-start mb-4">
              <div className="flex items-center gap-3">
                <div className={`p-2 rounded-lg ${s.enabled !== false ? 'bg-green-100 text-green-600' : 'bg-slate-100 text-slate-500'}`}>
                  <Calendar className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-semibold text-slate-900 dark:text-slate-100">{s.name || `Task ${idx + 1}`}</h3>
                  <p className="text-xs text-slate-500 mt-0.5">{s.cron || `Interval: ${s.interval}s`}</p>
                </div>
              </div>
              <span className={`text-xs px-2 py-1 rounded font-medium ${s.status === 'running' ? 'bg-blue-100 text-blue-700' : 'bg-slate-100 text-slate-600'}`}>
                {s.status === 'running' ? (
                  <span className="flex items-center gap-1">
                    <RefreshCw className="w-3 h-3 animate-spin" /> Running
                  </span>
                ) : 'Idle'}
              </span>
            </div>

            <div className="bg-slate-50 dark:bg-slate-900/50 p-3 rounded-lg border border-slate-100 dark:border-slate-800 font-mono text-xs text-slate-700 dark:text-slate-300 space-y-1 mb-4">
              <div className="flex justify-between items-center"><span className="opacity-50">Action</span> <span>{s.action}</span></div>
              <div className="flex justify-between items-center"><span className="opacity-50">Target Nodes</span> <span className="truncate max-w-[120px]">{Array.isArray(s.params?.targets) ? s.params.targets.join(', ') : 'Dynamic'}</span></div>
            </div>

            <div className="flex justify-end gap-2 border-t border-slate-100 dark:border-slate-800 pt-3">
              <button 
                className="px-3 py-1.5 text-sm font-medium border border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300 rounded transition-colors flex items-center gap-1.5"
                title={s.enabled !== false ? 'Disable Task' : 'Enable Task'}
              >
                {s.enabled !== false ? <StopCircle className="w-4 h-4 text-orange-500" /> : <PlayCircle className="w-4 h-4 text-green-500" />}
                {s.enabled !== false ? 'Pause' : 'Resume'}
              </button>
            </div>
          </div>
        ))}
      </div>

      {schedList.length === 0 && (
        <div className="text-center py-16 bg-white dark:bg-slate-950 rounded-xl border border-dashed border-slate-300 dark:border-slate-800">
           <p className="text-slate-500 dark:text-slate-400">No scheduled tasks found.</p>
        </div>
      )}
    </div>
  );
}
