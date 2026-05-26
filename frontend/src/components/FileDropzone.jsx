import { useState, useRef } from "react";
import { UploadIcon } from "../common/Icons";

export function FileDropzone({ label, tag, accept = "image/*", onFile }) {
  const [dragging, setDragging] = useState(false);
  const [preview,  setPreview]  = useState(null);
  const inputRef = useRef();

  const handleFile = (file) => {
    if (!file) return;
    const url = URL.createObjectURL(file);
    setPreview(url);
    onFile?.(file, url);
  };

  const onDrop = (e) => {
    e.preventDefault();
    setDragging(false);
    handleFile(e.dataTransfer.files[0]);
  };

  return (
    <div
      className={`
        relative flex-1 rounded-xl border-2 border-dashed transition-all duration-200 overflow-hidden cursor-pointer
        ${dragging
          ? "border-[#00E6E6] bg-[#00E6E6]/5 scale-[1.01]"
          : "border-[#4A4D52] bg-[#37393D] hover:border-[#00E6E6]/50 hover:bg-[#3D4044]"
        }
      `}
      style={{ minHeight: "180px" }}
      onDragOver={e => { e.preventDefault(); setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onDrop={onDrop}
      onClick={() => inputRef.current?.click()}
    >
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        className="hidden"
        onChange={e => handleFile(e.target.files[0])}
      />

      {preview ? (
        /* Loaded preview */
        <>
          <img src={preview} alt={label} className="absolute inset-0 w-full h-full object-cover" />
          <div className="absolute inset-0 bg-gradient-to-t from-[#2C2D30]/80 via-transparent to-transparent" />
          <div className="absolute bottom-0 left-0 right-0 px-4 py-3 flex items-center justify-between">
            <span className="text-white text-xs font-semibold">{label}</span>
            <span className="bg-[#008080] text-white text-[0.6rem] font-bold px-2 py-0.5 rounded-full">{tag}</span>
          </div>
          {/* Replace hint */}
          <div className="absolute inset-0 flex items-center justify-center opacity-0 hover:opacity-100 transition-opacity bg-black/40">
            <span className="text-white text-xs font-semibold bg-white/10 px-4 py-2 rounded-lg border border-white/20">
              Click to replace
            </span>
          </div>
        </>
      ) : (
        /* Empty state */
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 p-6">
          {/* Dashed inner frame hint */}
          <div className={`
            w-12 h-12 rounded-xl flex items-center justify-center transition-colors duration-200
            ${dragging ? "bg-[#00E6E6]/20 text-[#00E6E6]" : "bg-[#2C2D30] text-[#6B7280]"}
          `}>
            <UploadIcon size={22} />
          </div>
          <div className="text-center">
            <p className={`text-sm font-semibold transition-colors ${dragging ? "text-[#00E6E6]" : "text-[#9CA3AF]"}`}>
              {label}
            </p>
            <p className="text-[#4B5563] text-[0.65rem] mt-1">
              Drag & drop or click to upload
            </p>
            <p className="text-[#374151] text-[0.6rem] mt-0.5">PNG, JPG, GeoTIFF · max 50 MB</p>
          </div>
          <span className={`
            text-[0.62rem] font-bold px-3 py-1 rounded-full border transition-colors
            ${dragging
              ? "bg-[#00E6E6]/10 text-[#00E6E6] border-[#00E6E6]/30"
              : "bg-[#2C2D30] text-[#6B7280] border-[#4A4D52]"
            }
          `}>
            {tag}
          </span>
        </div>
      )}
    </div>
  );
}
