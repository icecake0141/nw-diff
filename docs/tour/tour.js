/*
 * Copyright 2026 NW-Diff Contributors
 * SPDX-License-Identifier: Apache-2.0
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * This file was created or modified with the assistance of an AI (Large Language Model).
 * Review required for correctness, security, and licensing.
 */

const translations = {
  en: {
    navWorkflow: "Workflow",
    navScreenshots: "Screenshots",
    navOperate: "Operate",
    heroEyebrow: "Network change verification, from capture to diff",
    heroTitle: "See every network change before it becomes an outage.",
    heroText:
      "NW-Diff turns device snapshots into an operator-friendly review flow: capture the before state, capture the after state, compare command output, and keep logs close when investigation is needed.",
    heroPrimary: "Explore the UI",
    heroSecondary: "Read setup guide",
    heroCaption: "The v2 control panel keeps batch actions, progress, and host coverage visible.",
    workflowEyebrow: "Guided operating flow",
    workflowTitle: "A tour built around the way network teams review changes.",
    stepOneTitle: "Load the device inventory",
    stepOneText: "Start from a CSV inventory and see every host, model, and capture state in one table.",
    stepTwoTitle: "Capture origin and destination",
    stepTwoText:
      "Run before and after captures across all hosts or target a single device when the change window is narrow.",
    stepThreeTitle: "Compare command output",
    stepThreeText:
      "Open host detail to inspect per-command deltas, timestamps, and unchanged output without leaving the UI.",
    stepFourTitle: "Trace operational evidence",
    stepFourText: "Use logs and task history to confirm what ran, when it ran, and which device needs follow-up.",
    screensEyebrow: "Product screenshots",
    screensTitle: "The interface stays focused on evidence, not decoration.",
    controlTitle: "Control panel for live coverage",
    controlText:
      "Operators can start origin or destination captures, monitor the current task, filter hosts, and confirm per-command coverage without opening separate tooling.",
    detailTitle: "Host detail for command-level review",
    detailText:
      "The host view brings inventory metadata, capture actions, comparison summaries, and command output into a single evidence trail for one network device.",
    logsTitle: "Logs for investigation and handoff",
    logsText:
      "Runtime logs are close to the workflow, so failed captures and deployment checks can be investigated with context instead of switching to a terminal first.",
    operateEyebrow: "Run it locally",
    operateTitle: "Start the v2 UI and follow the same tour with your devices.",
    operateText: "Open http://127.0.0.1:5000/v2 after startup.",
    footerText: "NW-Diff is an Apache-2.0 network capture and diff project.",
  },
  ja: {
    navWorkflow: "流れ",
    navScreenshots: "画面",
    navOperate: "起動",
    heroEyebrow: "キャプチャから差分確認まで、ネットワーク変更を検証",
    heroTitle: "障害になる前に、ネットワーク変更を見える化する。",
    heroText:
      "NW-Diffは機器スナップショットを運用者向けの確認フローに変換します。変更前を取得し、変更後を取得し、コマンド出力を比較し、調査に必要なログも同じ流れで確認できます。",
    heroPrimary: "UIを見る",
    heroSecondary: "セットアップを読む",
    heroCaption: "v2コントロールパネルでは、一括操作、進捗、ホスト別の取得状況を同じ画面で確認できます。",
    workflowEyebrow: "運用フロー",
    workflowTitle: "ネットワークチームの変更確認に合わせたユーザーエクスペリエンスツアー。",
    stepOneTitle: "機器インベントリを読み込む",
    stepOneText: "CSVインベントリから開始し、ホスト、モデル、キャプチャ状態を1つの表で確認します。",
    stepTwoTitle: "OriginとDestinationを取得",
    stepTwoText: "全ホストの変更前後キャプチャを実行できます。短い変更ウィンドウでは単一ホストだけを対象にできます。",
    stepThreeTitle: "コマンド出力を比較",
    stepThreeText: "ホスト詳細で、コマンド単位の差分、タイムスタンプ、変化のない出力をUI上で確認できます。",
    stepFourTitle: "運用証跡を追跡",
    stepFourText: "ログとタスク履歴から、何がいつ実行され、どの機器に追加確認が必要かを確認します。",
    screensEyebrow: "プロダクト画面",
    screensTitle: "装飾ではなく、判断材料に集中したインターフェース。",
    controlTitle: "取得状況を見渡すコントロールパネル",
    controlText:
      "運用者はOrigin/Destination取得、現在のタスク監視、ホスト絞り込み、コマンド単位の取得状況確認を別ツールなしで行えます。",
    detailTitle: "コマンド単位で確認するホスト詳細",
    detailText:
      "ホスト画面では、インベントリ情報、取得操作、比較サマリ、コマンド出力を1台分の証跡としてまとめて確認できます。",
    logsTitle: "調査と引き継ぎのためのログ",
    logsText:
      "ランタイムログがワークフローの近くにあるため、失敗した取得やデプロイ確認を文脈付きで調査できます。",
    operateEyebrow: "ローカル起動",
    operateTitle: "v2 UIを起動し、自分の機器で同じツアーをたどる。",
    operateText: "起動後に http://127.0.0.1:5000/v2 を開きます。",
    footerText: "NW-DiffはApache-2.0ライセンスのネットワークキャプチャ/差分プロジェクトです。",
  },
};

const setLanguage = (lang) => {
  const dictionary = translations[lang] || translations.en;
  document.documentElement.lang = lang;
  document.querySelectorAll("[data-i18n]").forEach((node) => {
    const key = node.getAttribute("data-i18n");
    if (dictionary[key]) {
      node.textContent = dictionary[key];
    }
  });
  document.querySelectorAll(".lang-button").forEach((button) => {
    const isActive = button.dataset.lang === lang;
    button.classList.toggle("active", isActive);
    button.setAttribute("aria-pressed", String(isActive));
  });
  localStorage.setItem("nwDiffTourLang", lang);
};

document.querySelectorAll(".lang-button").forEach((button) => {
  button.addEventListener("click", () => setLanguage(button.dataset.lang));
});

setLanguage(localStorage.getItem("nwDiffTourLang") || "en");
