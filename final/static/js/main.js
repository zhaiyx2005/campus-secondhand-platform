document.addEventListener("DOMContentLoaded", () => {
    const scrollStoragePrefix = "campus_scroll:";
    const scrollKey = `${scrollStoragePrefix}${window.location.pathname}${window.location.search}`;

    const restoreScrollPosition = () => {
        const rawPosition = sessionStorage.getItem(scrollKey);
        if (!rawPosition) {
            return;
        }

        sessionStorage.removeItem(scrollKey);
        const position = Number.parseInt(rawPosition, 10);
        if (Number.isNaN(position) || position <= 0) {
            return;
        }

        requestAnimationFrame(() => {
            window.scrollTo({ top: position, left: 0, behavior: "auto" });
        });
    };

    const saveScrollPosition = () => {
        sessionStorage.setItem(scrollKey, String(window.scrollY || window.pageYOffset || 0));
    };

    restoreScrollPosition();

    document.addEventListener("submit", (event) => {
        const form = event.target;
        if (!(form instanceof HTMLFormElement)) {
            return;
        }
        saveScrollPosition();
    }, true);

    document.addEventListener("click", (event) => {
        const button = event.target.closest("button[type='submit'], input[type='submit']");
        if (button) {
            saveScrollPosition();
            return;
        }

        const link = event.target.closest("a[href]");
        if (!link) {
            return;
        }

        const targetUrl = new URL(link.href, window.location.href);
        const currentUrl = new URL(window.location.href);
        const isSamePage = targetUrl.origin === currentUrl.origin
            && targetUrl.pathname === currentUrl.pathname
            && targetUrl.search === currentUrl.search;
        if (isSamePage && targetUrl.hash === currentUrl.hash) {
            saveScrollPosition();
        }
    }, true);

    const loginForm = document.querySelector("[data-login-form]");
    if (loginForm) {
        const accountInput = loginForm.querySelector("#account");
        const passwordInput = loginForm.querySelector("#password");
        const rememberInput = loginForm.querySelector("#remember_password");

        const savedAccount = localStorage.getItem("campus_account");
        const savedPassword = localStorage.getItem("campus_password");
        if (savedAccount && savedPassword) {
            accountInput.value = savedAccount;
            passwordInput.value = savedPassword;
            rememberInput.checked = true;
        }

        loginForm.addEventListener("submit", () => {
            if (rememberInput.checked) {
                localStorage.setItem("campus_account", accountInput.value);
                localStorage.setItem("campus_password", passwordInput.value);
            } else {
                localStorage.removeItem("campus_account");
                localStorage.removeItem("campus_password");
            }
        });
    }

    const publishForm = document.querySelector("[data-publish-form]");
    if (publishForm) {
        const imageInput = publishForm.querySelector("#images");
        const imageHelp = publishForm.querySelector("#imageHelp");
        const titleInput = publishForm.querySelector("#title");
        const descriptionInput = publishForm.querySelector("#description");
        const tagsInput = publishForm.querySelector("#tags");
        const aiTagsButton = publishForm.querySelector("[data-ai-tags-button]");
        const aiTagsStatus = publishForm.querySelector("[data-ai-tags-status]");

        imageInput.addEventListener("change", () => {
            const count = imageInput.files.length;
            if (count === 0) {
                imageHelp.textContent = "支持 jpg、jpeg、png、gif，至少 1 张，最多 6 张。";
                imageHelp.className = "form-text";
            } else if (count > 6) {
                imageHelp.textContent = `当前选择 ${count} 张，最多只能上传 6 张。`;
                imageHelp.className = "form-text text-danger";
            } else {
                imageHelp.textContent = `已选择 ${count} 张图片。`;
                imageHelp.className = "form-text text-success";
            }
        });

        if (aiTagsButton && tagsInput && descriptionInput) {
            aiTagsButton.addEventListener("click", async () => {
                const title = titleInput ? titleInput.value.trim() : "";
                const description = descriptionInput.value.trim();
                if (!title && !description) {
                    aiTagsStatus.textContent = "请先填写商品标题或描述。";
                    aiTagsStatus.className = "form-text text-danger";
                    return;
                }

                aiTagsButton.disabled = true;
                aiTagsStatus.textContent = "正在生成标签...";
                aiTagsStatus.className = "form-text text-muted";

                try {
                    const response = await fetch("/ai/product-tags", {
                        method: "POST",
                        headers: {
                            "Content-Type": "application/json",
                        },
                        body: JSON.stringify({ title, description }),
                    });
                    const data = await response.json();
                    if (!response.ok || !data.ok) {
                        throw new Error(data.message || "标签生成失败。");
                    }
                    tagsInput.value = data.tags.join(" ");
                    aiTagsStatus.textContent = "标签已生成，可继续手动调整。";
                    aiTagsStatus.className = "form-text text-success";
                } catch (error) {
                    aiTagsStatus.textContent = error.message || "标签生成失败，请稍后再试。";
                    aiTagsStatus.className = "form-text text-danger";
                } finally {
                    aiTagsButton.disabled = false;
                }
            });
        }
    }

    const chatWidget = document.querySelector("[data-chat-widget]");
    if (chatWidget) {
        chatWidget.querySelectorAll("[data-chat-toggle]").forEach((button) => {
            button.addEventListener("click", () => {
                chatWidget.classList.toggle("is-open");
            });
        });

        const messages = chatWidget.querySelector(".chat-messages");
        if (messages) {
            messages.scrollTop = messages.scrollHeight;
        }
    }
});
