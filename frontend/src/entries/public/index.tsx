import React from 'react';
import ReactDOM from 'react-dom/client';
import { usePublicStore } from '../../store/publicStore';
import { PublicOverview, PublicDetail } from '../../pages/public/Overview';
import { Activity, ShieldCheck, ArrowLeft } from 'lucide-react';
import '../../index.css';

function PublicApp() {
  const { pageInfo } = usePublicStore();
  const buildLabel = (window as any).panel_build_label || 'development';

  return (
    <div className="min-h-screen flex flex-col bg-slate-50 dark:bg-slate-900 text-slate-900 dark:text-slate-100 font-sans selection:bg-blue-100 dark:selection:bg-blue-900">
      <header className="sticky top-0 z-50 bg-white/80 dark:bg-slate-950/80 backdrop-blur-md border-b border-slate-200 dark:border-slate-800 px-4 md:px-8 h-16 flex items-center justify-between shadow-sm">
         <div className="flex items-center space-x-4">
           {pageInfo?.kind !== 'overview' && (
             <a href="/" className="mr-2 p-1.5 rounded-full hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors text-slate-500" title="Back to Overview">
               <ArrowLeft className="w-5 h-5" />
             </a>
           )}
           <div className="bg-blue-600 p-2 rounded-lg text-white">
             <Activity className="w-5 h-5" />
           </div>
           <div>
             <h1 className="font-bold text-lg leading-tight tracking-tight">Status Display</h1>
             <p className="text-[10px] uppercase font-bold tracking-wider text-slate-500 flex items-center mt-0.5">
               <ShieldCheck className="w-3 h-3 mr-1 inline" /> Public Board
             </p>
           </div>
         </div>
         
         <div className="flex items-center gap-3">
           <a href="/login" className="text-sm font-medium text-slate-600 hover:text-blue-600 dark:text-slate-400 dark:hover:text-blue-400 transition-colors border border-slate-200 dark:border-slate-700 px-3 py-1.5 rounded-full hover:border-blue-200 hover:bg-blue-50 dark:hover:bg-blue-900/20">
              Admin Login
           </a>
         </div>
      </header>

      <main className="flex-1 w-full max-w-6xl mx-auto p-4 md:p-8">
         {pageInfo?.kind === 'overview' ? <PublicOverview /> : <PublicDetail />}
      </main>

      <footer className="py-6 border-t border-slate-200 dark:border-slate-800 text-center text-xs text-slate-400 font-mono mt-auto bg-white dark:bg-slate-950">
         FRP Network Status • Build {buildLabel}
      </footer>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <PublicApp />
  </React.StrictMode>
);
