import React from 'react'
import { useAuth } from '../state/auth.jsx'

export default function Notebook(){
  const { token } = useAuth()
  const src = `/lite/index.html?token=${encodeURIComponent(token)}&dataset_id=`
  return (
    <div className="space-y-4">
      <div className="text-2xl font-semibold">Notebook (JupyterLite)</div>
      <div className="text-sm text-slate-600">If JupyterLite is deployed at /lite, it will load below. This build provides the iframe hook.</div>
      <div className="card bg-amber-50 p-4 my-4">
        <div className="font-semibold mb-1">Hướng dẫn nhanh:</div>
        <ul className="list-disc ml-6 text-sm">
          <li>Notebook này chạy hoàn toàn trong trình duyệt (không cần cài server Jupyter).</li>
          <li>Chọn <b>dataset_id</b> trong URL để load dữ liệu mẫu.</li>
          <li>Có thể thử <code>!pip install package_name</code> để cài thêm thư viện (nếu được hỗ trợ bên trong JupyterLite).</li>
          <li>Chỉnh sửa, chạy mã Python như bình thường. Nếu bị lỗi kernel, refresh lại trang.</li>
        </ul>
      </div>
      <div className="h-[75vh]">
        <iframe title="JupyterLite" src={src} className="w-full h-full border rounded" sandbox="allow-scripts allow-same-origin allow-downloads"></iframe>
      </div>
    </div>
  )
}
