async function loadHistoryGallery() {

    const container = document.getElementById("history-gallery");

    try {
        const res = await fetch("/history/images");
        const data = await res.json();

        if (!res.ok) {
            console.error(data);
            return;
        }

        container.innerHTML = "";

        data.images.forEach(img => {

            const item = document.createElement("div");
            item.classList.add("history-content-gallery-item");

            item.innerHTML = `
                <img src="${img.url}" class="history-image" loading="lazy">
                <div class="history-image-meta">
                    <p>${img.filename ?? "Image"}</p>
                    <small>${img.uploaded_at ?? ""}</small>
                </div>
            `;

            container.appendChild(item);
        });

    } catch (err) {
        console.error("Gallery load failed:", err);
    }
}
