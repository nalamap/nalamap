// components/PlanDisplay.tsx
"use client";

import React, { useState, useEffect } from "react";
import { ExecutionPlan, PlanStep, ToolUpdate } from "../stores/chatInterfaceStore";
import { formatToolInput, formatToolName } from "./ToolProgressIndicator";

interface PlanDisplayProps {
  plan: ExecutionPlan;
  toolUpdates?: ToolUpdate[];
}

/**
 * Displays the agent's multi-step execution plan with live status updates.
 * Shows each step with its current status (pending, in-progress, complete, etc.)
 * and animates transitions as the agent progresses through the plan.
 */
const PlanDisplay: React.FC<PlanDisplayProps> = ({ plan, toolUpdates = [] }) => {
  const completedSteps = plan.steps.filter((s) => s.status === "complete").length;
  const totalSteps = plan.steps.length;
  const progressPercent = totalSteps > 0 ? (completedSteps / totalSteps) * 100 : 0;

  return (
    <div className="plan-display-container">
      {/* Header with goal and progress */}
      <div className="plan-display-header">
        <div className="plan-display-header-top">
          <span className="plan-display-label">EXECUTION PLAN</span>
          <span className="plan-display-progress-text">
            {completedSteps}/{totalSteps} steps
          </span>
        </div>
        <div className="plan-display-goal">{plan.goal}</div>
        {/* Progress bar */}
        <div className="plan-display-progress-bar">
          <div
            className="plan-display-progress-fill"
            style={{ width: `${progressPercent}%` }}
          />
        </div>
      </div>

      {/* Steps list */}
      <div className="plan-display-steps">
        {plan.steps.map((step, index) => (
          <PlanStepItem
            key={step.step_number}
            step={step}
            isLast={index === plan.steps.length - 1}
            toolUpdates={toolUpdates}
          />
        ))}
      </div>
    </div>
  );
};

/**
 * Individual plan step with status icon, connecting line, and collapsible tool details.
 */
const PlanStepItem: React.FC<{ step: PlanStep; isLast: boolean; toolUpdates: ToolUpdate[] }> = ({
  step,
  isLast,
  toolUpdates,
}) => {
  const stepTools = toolUpdates.filter((t) => t.plan_step === step.step_number);
  const [toolsExpanded, setToolsExpanded] = useState(false);

  // Auto-expand when step is in-progress, auto-collapse when complete
  useEffect(() => {
    if (step.status === "in-progress") {
      setToolsExpanded(true);
    } else if (step.status === "complete" || step.status === "error") {
      setToolsExpanded(false);
    }
  }, [step.status]);

  return (
    <div className={`plan-step-item plan-step-${step.status}`}>
      {/* Step indicator with connecting line */}
      <div className="plan-step-indicator-col">
        <div className="plan-step-icon">
          <StepStatusIcon status={step.status} />
        </div>
        {!isLast && <div className="plan-step-connector" />}
      </div>

      {/* Step content */}
      <div className="plan-step-content">
        <div className="plan-step-title">
          <span className="plan-step-number">Step {step.step_number}</span>
          <span className="plan-step-title-text">{step.title}</span>
        </div>
        <div className="plan-step-description">{step.description}</div>
        {step.result_summary && step.status === "complete" && (
          <div className="plan-step-result">{step.result_summary}</div>
        )}

        {/* Collapsible tool details */}
        {stepTools.length > 0 && (
          <div className="plan-step-tools">
            <button
              className="plan-step-tools-toggle"
              onClick={() => setToolsExpanded(!toolsExpanded)}
            >
              <span className={`plan-step-tools-chevron ${toolsExpanded ? "expanded" : ""}`}>
                ▸
              </span>
              {stepTools.length} tool{stepTools.length !== 1 ? "s" : ""} used
            </button>
            {toolsExpanded && (
              <div className="plan-step-tools-list">
                {stepTools.map((tool, i) => {
                  const params = formatToolInput(tool.input);
                  return (
                    <div
                      key={i}
                      className={`plan-step-tool-item plan-step-tool-${tool.status}`}
                    >
                      <div className="plan-step-tool-icon">
                        {tool.status === "running" && (
                          <svg
                            className="tool-spinner"
                            viewBox="0 0 24 24"
                            fill="none"
                            xmlns="http://www.w3.org/2000/svg"
                          >
                            <circle
                              cx="12"
                              cy="12"
                              r="10"
                              stroke="currentColor"
                              strokeWidth="3"
                              strokeLinecap="round"
                              strokeDasharray="32 32"
                            >
                              <animateTransform
                                attributeName="transform"
                                type="rotate"
                                from="0 12 12"
                                to="360 12 12"
                                dur="1s"
                                repeatCount="indefinite"
                              />
                            </circle>
                          </svg>
                        )}
                        {tool.status === "complete" && (
                          <svg
                            className="tool-check"
                            viewBox="0 0 24 24"
                            fill="none"
                            xmlns="http://www.w3.org/2000/svg"
                          >
                            <path
                              d="M20 6L9 17L4 12"
                              stroke="currentColor"
                              strokeWidth="3"
                              strokeLinecap="round"
                              strokeLinejoin="round"
                            />
                          </svg>
                        )}
                        {tool.status === "error" && (
                          <svg
                            className="tool-error"
                            viewBox="0 0 24 24"
                            fill="none"
                            xmlns="http://www.w3.org/2000/svg"
                          >
                            <circle
                              cx="12"
                              cy="12"
                              r="10"
                              stroke="currentColor"
                              strokeWidth="3"
                            />
                            <path
                              d="M15 9L9 15M9 9L15 15"
                              stroke="currentColor"
                              strokeWidth="3"
                              strokeLinecap="round"
                            />
                          </svg>
                        )}
                      </div>
                      <div className="plan-step-tool-content">
                        <span className="plan-step-tool-name">
                          {formatToolName(tool.name)}
                        </span>
                        {params && (
                          <span className="plan-step-tool-params">{params}</span>
                        )}
                        {tool.error && (
                          <span className="plan-step-tool-error-msg">
                            {tool.error}
                          </span>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

/**
 * Status icon for each step state.
 */
const StepStatusIcon: React.FC<{ status: PlanStep["status"] }> = ({
  status,
}) => {
  switch (status) {
    case "pending":
      return (
        <div className="plan-icon-pending">
          <div className="plan-icon-dot" />
        </div>
      );
    case "in-progress":
      return (
        <svg
          className="plan-icon-spinner"
          viewBox="0 0 24 24"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          <circle
            cx="12"
            cy="12"
            r="10"
            stroke="currentColor"
            strokeWidth="3"
            strokeLinecap="round"
            strokeDasharray="32 32"
          >
            <animateTransform
              attributeName="transform"
              type="rotate"
              from="0 12 12"
              to="360 12 12"
              dur="1s"
              repeatCount="indefinite"
            />
          </circle>
        </svg>
      );
    case "complete":
      return (
        <svg
          className="plan-icon-check"
          viewBox="0 0 24 24"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          <circle cx="12" cy="12" r="10" fill="currentColor" opacity="0.15" />
          <path
            d="M8 12L11 15L16 9"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      );
    case "skipped":
      return (
        <svg
          className="plan-icon-skipped"
          viewBox="0 0 24 24"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2" strokeDasharray="4 3" />
          <path
            d="M8 12H16"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
          />
        </svg>
      );
    case "error":
      return (
        <svg
          className="plan-icon-error"
          viewBox="0 0 24 24"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          <circle cx="12" cy="12" r="10" fill="currentColor" opacity="0.15" />
          <path
            d="M15 9L9 15M9 9L15 15"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinecap="round"
          />
        </svg>
      );
    default:
      return <div className="plan-icon-dot" />;
  }
};

export default PlanDisplay;
