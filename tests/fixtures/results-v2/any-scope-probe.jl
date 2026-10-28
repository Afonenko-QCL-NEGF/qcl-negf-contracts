# Explicit development check; uses the prepared Core project, never a solver or bootstrap.
using Test
empty!(ARGS)
push!(ARGS,"--check")
include(normpath(joinpath(@__DIR__,"../../../tools/reflect_core_layout.jl")))

function reset_probe_cache!()
    empty!(NODES); empty!(TYPES)
    isdefined(Main,:VALIDATED) && empty!(VALIDATED)
    isdefined(Main,:VISITING) && empty!(VISITING)
end

@testset "Any is qualified by its owning field, never path text or cache" begin
    reset_probe_cache!()
    @test_throws ErrorException visit(Any,"UnqualifiedPublicType.value")
    reset_probe_cache!()
    @test_throws ErrorException visit(Dict{String,Any},"Unqualified.restart_contract")
    reset_probe_cache!()
    visit(SCBAResult,"SCBAResult")
    @test NODES["Any"] == Dict("kind"=>"dynamic","scope"=>"SCBAResult.restart_contract")
    @test_throws ErrorException visit(Any,"UnqualifiedPublicType.value")
    @test_throws ErrorException visit(Dict{String,Any},"UnqualifiedPublicType.value")
end
