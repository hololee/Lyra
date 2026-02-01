import axios from 'axios';
import { Clock, FileCode, Play, Trash2 } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Modal from '../components/Modal';

interface Template {
  id: string;
  name: string;
  description: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  config: any;
  created_at: string;
}

export default function Templates() {
  const navigate = useNavigate();
  const [templates, setTemplates] = useState<Template[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  // Modal State
  const [modalConfig, setModalConfig] = useState({
      isOpen: false,
      title: '',
      message: '',
      type: 'alert' as 'alert' | 'confirm',
      onConfirm: () => {}
  });

  const fetchTemplates = async () => {
    try {
      setIsLoading(true);
      const res = await axios.get('templates/');
      setTemplates(res.data);
    } catch (error) {
      console.error("Failed to fetch templates", error);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchTemplates();
  }, []);

  const handleDeleteClick = (id: string, name: string) => {
      setModalConfig({
          isOpen: true,
          title: 'Delete Template',
          message: `Are you sure you want to delete "${name}"? This action cannot be undone.`,
          type: 'confirm',
          onConfirm: () => handleDelete(id)
      });
  };

  const handleDelete = async (id: string) => {
      try {
          await axios.delete(`templates/${id}`);
          fetchTemplates();
      } catch (error) {
          console.error("Failed to delete template", error);
      } finally {
          setModalConfig(prev => ({ ...prev, isOpen: false }));
      }
  };

  const handleLoad = (template: Template) => {
      navigate('/provisioning', { state: { templateConfig: template.config } });
  };

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8">
      <Modal
          isOpen={modalConfig.isOpen}
          onClose={() => setModalConfig(prev => ({ ...prev, isOpen: false }))}
          title={modalConfig.title}
          message={modalConfig.message}
          type={modalConfig.type}
          onConfirm={modalConfig.onConfirm}
      />

      <header>
        <h2 className="text-3xl font-bold text-white tracking-tight">Templates</h2>
        <p className="text-gray-400 mt-1">Manage your saved environment configurations.</p>
      </header>

      {isLoading ? (
          <div className="text-center py-20">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-white mx-auto mb-4"></div>
              <p className="text-gray-400">Loading templates...</p>
          </div>
      ) : templates.length === 0 ? (
          <div className="bg-[#18181b] rounded-xl border border-[#27272a] p-12 text-center text-gray-400 flex flex-col items-center gap-4">
            <div className="p-4 bg-[#27272a] rounded-full">
                <FileCode size={32} className="text-gray-500" />
            </div>
            <div>
                <h3 className="text-lg font-semibold text-white mb-1">No Templates Found</h3>
                <p>Save your favorite configurations in the Provisioning tab.</p>
            </div>
            <button
                onClick={() => navigate('/provisioning')}
                className="mt-2 px-6 py-2 bg-[#27272a] hover:bg-[#3f3f46] text-white rounded-lg text-sm font-medium transition-colors"
            >
                Go to Provisioning
            </button>
          </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {templates.map((template) => (
            <div key={template.id} className="bg-[#18181b] rounded-xl border border-[#27272a] overflow-hidden group hover:border-[#3f3f46] transition-all hover:shadow-xl hover:shadow-black/50 hover:-translate-y-1">
              <div className="p-6 space-y-4">
                <div className="flex justify-between items-start">
                    <div className="p-2 bg-blue-500/10 rounded-lg text-blue-400 mb-2">
                        <FileCode size={24} />
                    </div>
                    {/* Timestamp */}
                    <div className="flex items-center gap-1.5 text-xs text-gray-500 bg-[#27272a] px-2 py-1 rounded">
                        <Clock size={12} />
                        {new Date(template.created_at).toLocaleDateString()}
                    </div>
                </div>

                <div>
                    <h3 className="text-xl font-bold text-white mb-1 truncate">{template.name}</h3>
                    <p className="text-sm text-gray-400 line-clamp-2 min-h-[40px]">
                        {template.description || "No description provided."}
                    </p>
                </div>

                <div className="pt-4 border-t border-[#27272a] flex gap-3">
                    <button
                        onClick={() => handleLoad(template)}
                        className="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-sm font-medium flex items-center justify-center gap-2 transition-colors"
                    >
                        <Play size={16} /> Load
                    </button>
                    <button
                        onClick={() => handleDeleteClick(template.id, template.name)}
                        className="px-3 py-2 bg-[#27272a] hover:bg-red-500/20 hover:text-red-400 text-gray-400 rounded-lg transition-colors border border-[#3f3f46] hover:border-red-500/50"
                        title="Delete Template"
                    >
                        <Trash2 size={16} />
                    </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
