/**
 * 主应用逻辑 - 课程列表页、首页
 */
document.addEventListener('DOMContentLoaded', () => {
    initAuth();
    loadCourses();
    setupSearch();
    loadContinueLearning();
});

let currentCourses = [];
let currentCategory = '';

async function loadCourses(category = '', search = '') {
    const container = document.getElementById('course-list');
    container.innerHTML = '<div class="text-center py-20 text-gray-400">加载中...</div>';

    try {
        const data = await CourseAPI.getList({ category, search, per_page: 50 });
        currentCourses = data.courses || [];
        const categories = data.categories || [];

        renderCategories(categories);
        renderCourses(currentCourses);
    } catch (err) {
        container.innerHTML = `<div class="text-center py-20 text-red-500">加载失败: ${err.message}</div>`;
    }
}

function renderCategories(categories) {
    const container = document.getElementById('category-filters');
    if (!container) return;

    const allBtn = document.createElement('button');
    allBtn.className = `px-4 py-2 rounded-full text-sm mr-2 mb-2 transition ${!currentCategory ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-700 hover:bg-gray-300'}`;
    allBtn.textContent = '全部';
    allBtn.onclick = () => { currentCategory = ''; loadCourses(); };

    container.innerHTML = '';
    container.appendChild(allBtn);

    categories.forEach(cat => {
        const btn = document.createElement('button');
        btn.className = `px-4 py-2 rounded-full text-sm mr-2 mb-2 transition ${currentCategory === cat ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-700 hover:bg-gray-300'}`;
        btn.textContent = cat;
        btn.onclick = () => { currentCategory = cat; loadCourses(cat); };
        container.appendChild(btn);
    });
}

function renderCourses(courses) {
    const container = document.getElementById('course-list');
    if (courses.length === 0) {
        container.innerHTML = '<div class="text-center py-20 text-gray-400">暂无课程</div>';
        return;
    }

    const user = JSON.parse(localStorage.getItem('user') || 'null');
    const isAdmin = user && user.role === 'admin';

    container.innerHTML = courses.map(course => {
        const progress = course.progress || 0;
        const coverUrl = course.cover_image
            ? (course.cover_image.startsWith('http') ? course.cover_image : `/uploads/covers/${course.cover_image.split('/').pop()}`)
            : 'https://placehold.co/400x250/e5e7eb/9ca3af?text=Audio+Course';

        return `
            <div class="bg-white rounded-xl shadow-sm hover:shadow-lg transition-shadow overflow-hidden cursor-pointer"
                 onclick="window.location.href='/player.html?course=${course.id}'">
                <div class="relative h-48 bg-gray-100 overflow-hidden">
                    <img src="${coverUrl}" alt="${course.title}" class="w-full h-full object-cover"
                         onerror="this.src='https://placehold.co/400x250/e5e7eb/9ca3af?text=Audio+Course'">
                    <div class="absolute bottom-0 left-0 right-0 h-1 bg-gray-200">
                        <div class="h-full bg-green-500 transition-all" style="width: ${progress}%"></div>
                    </div>
                    <span class="absolute top-3 right-3 px-2 py-1 bg-black/50 text-white text-xs rounded-full">${course.category}</span>
                </div>
                <div class="p-5">
                    <h3 class="font-bold text-lg text-gray-900 mb-2 truncate">${course.title}</h3>
                    <p class="text-gray-500 text-sm mb-3 line-clamp-2 h-10">${course.description || '暂无描述'}</p>
                    <div class="flex items-center justify-between text-sm text-gray-400">
                        <span>${course.audio_count || 0} 个音频</span>
                        <span>${formatDate(course.created_at)}</span>
                    </div>
                    ${progress > 0 ? `<div class="mt-3 text-sm text-green-600">已学习 ${progress.toFixed(1)}%</div>` : ''}
                </div>
            </div>
        `;
    }).join('');
}

async function loadContinueLearning() {
    const token = localStorage.getItem('access_token');
    if (!token) return;

    const container = document.getElementById('continue-learning');
    if (!container) return;

    try {
        const data = await PlayerAPI.getLastProgress();
        if (!data.has_progress) {
            container.style.display = 'none';
            return;
        }

        container.innerHTML = `
            <div class="bg-gradient-to-r from-blue-600 to-indigo-600 rounded-xl shadow-lg p-6 text-white mb-8 cursor-pointer hover:shadow-xl transition"
                 onclick="window.location.href='/player.html?course=${data.course_id}&audio=${data.audio_id}&t=${data.current_time}'">
                <div class="flex items-center justify-between">
                    <div>
                        <div class="text-blue-100 text-sm mb-1">继续学习</div>
                        <h2 class="text-xl font-bold mb-1">${escapeHtml(data.course_title)}</h2>
                        <p class="text-blue-100 text-sm">${escapeHtml(data.audio_title)} · ${formatDuration(data.current_time)}</p>
                    </div>
                    <div class="flex items-center justify-center w-14 h-14 bg-white/20 rounded-full">
                        <svg class="w-8 h-8 text-white" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>
                    </div>
                </div>
            </div>
        `;
        container.style.display = 'block';
    } catch (e) {
        container.style.display = 'none';
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function setupSearch() {
    const searchInput = document.getElementById('search-input');
    if (!searchInput) return;

    let debounceTimer;
    searchInput.addEventListener('input', (e) => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
            loadCourses(currentCategory, e.target.value.trim());
        }, 300);
    });
}
