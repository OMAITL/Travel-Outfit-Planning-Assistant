"""Assets node — Image + Shopping in parallel (XHS retrieval runs earlier in workflow)."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from src.graph.nodes.image import image_node
from src.graph.nodes.shopping import shopping_node
from src.graph.state import PlanningState


def assets_node(state: PlanningState) -> PlanningState:
    """Generate look images and fetch Taobao products in parallel."""
    input_errors_len = len(state.errors)
    input_trace_len = len(state.trace)
    state = state.append_trace("Assets", "running image + shopping in parallel")

    image_trace_start = len(state.trace) + 1
    image_errors_start = len(state.errors)

    with ThreadPoolExecutor(max_workers=2) as pool:
        image_future = pool.submit(image_node, state)
        shopping_future = pool.submit(shopping_node, state)
        image_result = image_future.result()
        shopping_result = shopping_future.result()

    child_traces = []
    child_errors = []
    for partial in (image_result, shopping_result):
        if partial is image_result:
            child_traces.extend(partial.trace[image_trace_start:])
            child_errors.extend(partial.errors[image_errors_start:])
        else:
            child_traces.extend(partial.trace[input_trace_len:])
            child_errors.extend(partial.errors[input_errors_len:])

    return state.model_copy(
        update={
            "look_images": image_result.look_images,
            "products": shopping_result.products,
            "errors": [*state.errors, *child_errors],
            "trace": [*state.trace, *child_traces],
        }
    ).append_trace("Assets", "assets complete")
