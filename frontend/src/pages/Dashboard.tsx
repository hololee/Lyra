import axios from 'axios';
import { HardDrive, LayoutTemplate, Network, RefreshCw, SquareTerminal, Trash2, X } from 'lucide-react';
import { useEffect, useState } from 'react';
import Modal from '../components/Modal';

interface MountConfig {
  host_path: string;
  container_path: string;
  mode: string;
}

interface Environment {
  id: string;
  name: string;
  status: string;
  gpu_indices: number[];
  ssh_port: number;
  jupyter_port: number;
  created_at: string;
  mount_config: MountConfig[];
}

export default function Dashboard() {
  const [environments, setEnvironments] = useState<Environment[]>([]);
  const [loading, setLoading] = useState(true);
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [selectedVolEnv, setSelectedVolEnv] = useState<Environment | null>(null);

  const fetchEnvironments = async () => {
    try {
      setLoading(true);
      const res = await axios.get('environments/');
      setEnvironments(res.data);
    } catch (error) {
      console.error("Failed to fetch environments", error);
    } finally {
      setLoading(false);
    }
  };

  const deleteEnvironment = async () => {
    if (!deleteId) return;
    try {
        await axios.delete(`environments/${deleteId}`);
        fetchEnvironments();
    } catch (error) {
        console.error("Failed to delete environment", error);
        // Could also add an error modal here
    }
    setDeleteId(null);
  };

  useEffect(() => {
    fetchEnvironments();
    const interval = setInterval(fetchEnvironments, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="p-8 space-y-8 relative">
      <Modal
        isOpen={!!deleteId}
        onClose={() => setDeleteId(null)}
        onConfirm={deleteEnvironment}
        title="Delete Environment"
        message="Are you sure you want to delete this environment? This action cannot be undone and will permanently remove the container and data."
        isDestructive={true}
      />

      {/* Volume Details Modal */}
      {selectedVolEnv && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
            <div className="bg-[#18181b] rounded-xl border border-[#3f3f46] shadow-2xl w-full max-w-lg overflow-hidden animate-in fade-in zoom-in duration-200">
                <div className="p-6 border-b border-[#3f3f46] flex justify-between items-center">
                    <h3 className="text-xl font-bold text-white flex items-center gap-2">
                        <HardDrive size={20} className="text-blue-400" />
                        Volume Mounts
                    </h3>
                    <button onClick={() => setSelectedVolEnv(null)} className="text-gray-400 hover:text-white transition-colors">
                        <X size={20} />
                    </button>
                </div>
                <div className="p-6">
                    <p className="text-gray-400 text-sm mb-4">
                        Mounted volumes for <span className="text-white font-medium">{selectedVolEnv.name}</span>
                    </p>
                    <div className="space-y-3">
                        {selectedVolEnv.mount_config.map((mount, idx) => (
                            <div key={idx} className="bg-[#27272a] p-3 rounded-lg border border-[#3f3f46] text-sm">
                                <div className="flex items-center gap-2 mb-1">
                                    <span className="text-xs font-bold text-blue-400 uppercase w-10 shrink-0">Host</span>
                                    <span className="text-gray-300 font-mono overflow-x-auto whitespace-nowrap flex-1 scrollbar-hide">{mount.host_path}</span>
                                </div>
                                <div className="flex items-center gap-2">
                                    <span className="text-xs font-bold text-green-400 uppercase w-10 shrink-0">Dest</span>
                                    <span className="text-gray-300 font-mono overflow-x-auto whitespace-nowrap flex-1 scrollbar-hide">{mount.container_path}</span>
                                    <span className="ml-auto text-[10px] bg-[#3f3f46] px-1.5 py-0.5 rounded text-gray-400 uppercase">
                                        {mount.mode}
                                    </span>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
                <div className="p-4 border-t border-[#3f3f46] bg-[#27272a]/50 flex justify-end">
                    <button
                        onClick={() => setSelectedVolEnv(null)}
                        className="px-4 py-2 rounded-lg text-sm font-medium bg-blue-600 hover:bg-blue-500 text-white shadow-lg shadow-blue-500/20 transition-all"
                    >
                        Close
                    </button>
                </div>
            </div>
        </div>
      )}

      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-3xl font-bold text-white">Dashboard</h2>
          <p className="text-gray-400 mt-1">Manage your GPU virtual environments</p>
      </div>
    </div>


      <div className="bg-[#27272a] rounded-xl border border-[#3f3f46] overflow-hidden">
        <div className="p-6 border-b border-[#3f3f46] flex justify-between items-center">
            <h3 className="text-xl font-bold text-white">Instances</h3>
            <button onClick={fetchEnvironments} className="p-2 hover:bg-[#3f3f46] rounded-full text-gray-400 transition-colors">
                <RefreshCw size={18} className={loading && environments.length > 0 ? "animate-spin" : ""} />
            </button>
        </div>
        <div className="w-full text-left">
            {loading && environments.length === 0 ? (
                 <div className="p-8 text-center text-gray-500">Loading environments...</div>
            ) : environments.length === 0 ? (
                 <div className="p-8 text-center text-gray-500">No environments found.</div>
            ) : (
                <table className="w-full">
                    <thead className="bg-[#18181b] text-gray-400 text-sm uppercase">
                        <tr>
                            <th className="px-6 py-4 font-medium">Name</th>
                            <th className="px-6 py-4 font-medium">Status</th>
                            <th className="px-6 py-4 font-medium">Ports (SSH/Jupyter)</th>
                            <th className="px-6 py-4 font-medium">GPU</th>
                            <th className="px-6 py-4 font-medium text-right">Actions</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-[#3f3f46]">
                        {environments.map((env) => (
                            <tr key={env.id} className="hover:bg-[#3f3f46]/50 transition-colors">
                                <td className="px-6 py-4 text-white font-medium">{env.name}</td>
                                <td className="px-6 py-4">
                                    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                                        env.status === 'running' ? 'bg-green-500/10 text-green-500' :
                                        env.status === 'building' ? 'bg-yellow-500/10 text-yellow-500' :
                                        'bg-red-500/10 text-red-500'
                                    }`}>
                                        {env.status.charAt(0).toUpperCase() + env.status.slice(1)}
                                    </span>
                                </td>
                                <td className="px-6 py-4 text-gray-300">
                                    <div className="flex items-center gap-3">
                                        <div className="flex items-center gap-1.5" title="SSH Port">
                                            <span>{env.ssh_port}</span>
                                            <button
                                                className="p-1 hover:bg-[#3f3f46] rounded text-gray-500 hover:text-blue-400 transition-colors"
                                                title="Connect via SSH (Coming Soon)"
                                            >
                                                <SquareTerminal size={14} />
                                            </button>
                                        </div>
                                        <span className="text-gray-600">/</span>
                                        <div className="flex items-center gap-1.5" title="Jupyter Port">
                                            <span>{env.jupyter_port}</span>
                                            <button
                                                className="p-1 hover:bg-[#3f3f46] rounded text-gray-500 hover:text-orange-400 transition-colors"
                                                title="Open Jupyter Lab (Coming Soon)"
                                            >
                                                <LayoutTemplate size={14} />
                                            </button>
                                        </div>
                                    </div>
                                </td>
                                <td className="px-6 py-4 text-gray-300">
                                    {env.gpu_indices.length > 0 ? env.gpu_indices.join(', ') : "-"}
                                </td>
                                <td className="px-6 py-4 text-right space-x-2">
                                    <button
                                        onClick={() => {
                                            if (env.mount_config && env.mount_config.length > 0) {
                                                setSelectedVolEnv(env);
                                            }
                                        }}
                                        disabled={!env.mount_config || env.mount_config.length === 0}
                                        className={`p-2 rounded-lg transition-colors ${
                                            env.mount_config && env.mount_config.length > 0
                                            ? "text-gray-400 hover:text-blue-400 hover:bg-blue-500/10"
                                            : "text-gray-600 cursor-not-allowed opacity-30"
                                        }`}
                                        title={env.mount_config && env.mount_config.length > 0 ? "View Volumes" : "No Volumes"}
                                    >
                                        <HardDrive size={18} />
                                    </button>
                                    <button
                                        className="p-2 hover:bg-[#3f3f46] rounded-lg text-gray-400 hover:text-purple-400 transition-colors"
                                        title="Manage Ports (Coming Soon)"
                                    >
                                        <Network size={18} />
                                    </button>
                                    <button
                                        onClick={() => setDeleteId(env.id)}
                                        className="p-2 hover:bg-gray-700 rounded-lg text-gray-400 hover:text-red-400 transition-colors"
                                        title="Delete"
                                    >
                                        <Trash2 size={18} />
                                    </button>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            )}
        </div>
      </div>
    </div>
  );
}
