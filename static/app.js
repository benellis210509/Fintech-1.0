document.addEventListener("DOMContentLoaded", function () {
    const navToggle = document.querySelector(".js-nav-toggle");
    if (navToggle) {
        navToggle.addEventListener("click", function () {
            document.body.classList.toggle("nav-open");
        });
    }

    const toast = document.getElementById("globalToast");
    if (toast) {
        window.setTimeout(function () {
            toast.classList.add("toast-hide");
        }, 3800);
    }

    document.querySelectorAll("form[data-confirm]").forEach(function (form) {
        form.addEventListener("submit", function (event) {
            if (!window.confirm(form.dataset.confirm || "Are you sure?")) {
                event.preventDefault();
            }
        });
    });

    document.querySelectorAll(".js-toggle-edit").forEach(function (button) {
        button.addEventListener("click", function () {
            const panel = document.getElementById(button.dataset.editTarget || "");
            if (panel) {
                panel.hidden = !panel.hidden;
            }
        });
    });

    const fileInput = document.getElementById("file-upload");
    const selectedFile = document.getElementById("selectedFile");
    if (fileInput && selectedFile) {
        fileInput.addEventListener("change", function () {
            const file = fileInput.files && fileInput.files[0];
            if (!file) {
                selectedFile.hidden = true;
                selectedFile.textContent = "";
                return;
            }
            selectedFile.hidden = false;
            selectedFile.textContent = "";
            const name = document.createElement("strong");
            name.textContent = file.name;
            const size = document.createElement("span");
            size.textContent = (file.size / 1024).toFixed(1) + " KB";
            selectedFile.append(name, size);
        });
    }

    const uploadForm = document.getElementById("uploadForm");
    if (uploadForm) {
        uploadForm.addEventListener("submit", function () {
            const submitButton = uploadForm.querySelector('button[type="submit"]');
            if (submitButton && submitButton.disabled) {
                return;
            }
            const overlay = document.getElementById("processingOverlay");
            if (overlay) {
                overlay.hidden = false;
                document.body.classList.add("is-processing");
            }
            const processingText = document.getElementById("processingText");
            const messages = [
                "Reading and validating your CSV...",
                "Checking holdings and currency...",
                "Loading available market data...",
                "Calculating portfolio metrics...",
                "Generating your report...",
            ];
            let index = 0;
            window.setInterval(function () {
                index = Math.min(index + 1, messages.length - 1);
                if (processingText) {
                    processingText.textContent = messages[index];
                }
            }, 2600);
        });
    }
});
