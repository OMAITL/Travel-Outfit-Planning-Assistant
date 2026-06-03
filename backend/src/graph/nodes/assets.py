"""Assets node — run Image and Shopping agents in parallel."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from src.graph.nodes.image import image_node
from src.graph.nodes.shopping import shopping_node
from src.graph.state import PlanningState


def assets_node(state: PlanningState) -> PlanningState:
    """Generate look images and fetch products concurrently."""
    input_errors_len = len(state.errors)
    input_trace_len = len(state.trace)
    state = state.append_trace("Assets", "running image and shopping in parallel")

    with ThreadPoolExecutor(max_workers=2) as pool:
        image_future = pool.submit(image_node, state)
        shopping_future = pool.submit(shopping_node, state)
        image_result = image_future.result()
        shopping_result = shopping_future.result()

    child_traces = []
    child_errors = []
    for partial in (image_result, shopping_result):
        child_traces.extend(partial.trace[input_trace_len:])
        child_errors.extend(partial.errors[input_errors_len:])

    return state.model_copy(
        update={
            "look_images": image_result.look_images,
            "products": shopping_result.products,
            "errors": [*state.errors, *child_errors],
            "trace": [*state.trace, *child_traces],
        }
    ).append_trace("Assets", "parallel assets complete")
