import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AdminLayout } from '../../components/layout/AdminLayout';
import { Dashboard } from '../../pages/admin/Dashboard';
import { Nodes } from '../../pages/admin/Nodes';
import { Paths } from '../../pages/admin/Paths';
import { Schedules } from '../../pages/admin/Schedules';
import '../../index.css';

function Settings() { return <div className="text-2xl font-bold text-slate-900">Settings (WIP)</div>; }
function Alerts() { return <div className="text-2xl font-bold text-slate-900">Alerts (WIP)</div>; }

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/admin" element={<AdminLayout />}>
          <Route index element={<Dashboard />} />
          <Route path="nodes" element={<Nodes />} />
          <Route path="paths" element={<Paths />} />
          <Route path="schedules" element={<Schedules />} />
          <Route path="settings" element={<Settings />} />
          <Route path="alerts" element={<Alerts />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </React.StrictMode>
);
